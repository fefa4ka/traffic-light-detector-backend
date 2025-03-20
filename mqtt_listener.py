import base64
import sqlite3
import time
from collections import defaultdict
from datetime import datetime

import paho.mqtt.client as mqtt
import telemetry_pb2

import register_detector

DB_PATH = "/data/detectors.db"
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "$me/device/state"
LISTENER_USERNAME = "listener"

# Cache for traffic light states
intersection_states = defaultdict(dict)

# Cache for detector configurations
_detector_cache = {}
_last_cache_update = 0

def get_traffic_light_config(detector_id):
    """Get traffic light configuration with caching."""
    global _last_cache_update
    
    # Refresh cache every 5 minutes
    if (datetime.now().timestamp() - _last_cache_update) > 300:
        _detector_cache.clear()
        
    if detector_id not in _detector_cache:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT tlc.light_id, tlc.channel_mask, tlc.signal_color, 
                   tl.intersection_id, tl.name, tl.location
            FROM traffic_light_channels tlc
            JOIN traffic_lights tl ON tlc.light_id = tl.light_id
            WHERE tlc.detector_id = ?
        """, (detector_id,))
        
        _detector_cache[detector_id] = cursor.fetchall()
        conn.close()
        _last_cache_update = datetime.now().timestamp()
        
    return _detector_cache[detector_id]

def process_traffic_states(detector_id, channels):
    """Process raw channels into traffic light states with intersection grouping."""
    config = get_traffic_light_config(detector_id)
    states = {}
    intersections = defaultdict(dict)
    
    for light_id, channel_mask, signal_color, intersection_id, name, location in config:
        # Determine if this signal is active
        is_active = bool(channels & channel_mask)
        
        # Initialize light state if not exists
        if light_id not in states:
            states[light_id] = {
                'name': name,
                'location': location,
                'red': False,
                'green': False,
                'intersection_id': intersection_id
            }
        
        # Update signal state with conflict detection
        if signal_color == 'RED':
            states[light_id]['red'] = is_active
            # Ensure green is off if red is on
            if is_active:
                states[light_id]['green'] = False
        elif signal_color == 'GREEN':
            states[light_id]['green'] = is_active
            # Ensure red is off if green is on
            if is_active:
                states[light_id]['red'] = False
            
        # Track state in intersection grouping
        light_state = 'RED' if states[light_id]['red'] else 'GREEN' if states[light_id]['green'] else 'UNKNOWN'
        intersections[intersection_id].setdefault('lights', {})[light_id] = {
            'name': name,
            'state': light_state,
            'location': location
        }
    
    # Determine intersection overall state
    for intersection_id, data in intersections.items():
        all_lights = list(data['lights'].values())
        red_lights = [l for l in all_lights if l['state'] == 'RED']
        
        # Intersection is considered RED if any light is RED
        intersections[intersection_id]['overall_state'] = 'RED' if red_lights else 'GREEN'
        intersections[intersection_id]['timestamp'] = datetime.now().isoformat()
    
    return {
        'lights': states,
        'intersections': dict(intersections)
    }

def save_telemetry(detector_id, channels, timestamp, counter):
    """Save telemetry data and process traffic states."""
    # Process traffic states first to check if any valid states exist
    processed = process_traffic_states(detector_id, channels)
    
    # Check if any lights have a valid state (not UNKNOWN)
    has_valid_states = False
    for light_id, light_data in processed['lights'].items():
        if light_data['red'] or light_data['green']:
            has_valid_states = True
            break
    
    # Only save telemetry if we have valid states
    if has_valid_states:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("INSERT INTO telemetry (detector_id, channels, timestamp, counter) VALUES (?, ?, ?, ?)",
                   (detector_id, channels, timestamp, counter))
    
    # Save individual light states
    for light_id, state in processed['lights'].items():
        # Only save states that are explicitly RED or GREEN
        current_state = "UNKNOWN"
        if state['red']:
            current_state = 'RED'
            cursor.execute("""
                INSERT INTO traffic_light_states (light_id, state, timestamp)
                VALUES (?, ?, ?)
            """, (light_id, current_state, timestamp))
        elif state['green']:
            current_state = 'GREEN'
            cursor.execute("""
                INSERT INTO traffic_light_states (light_id, state, timestamp)
                VALUES (?, ?, ?)
            """, (light_id, current_state, timestamp))

        # Only track state transitions for valid states (RED or GREEN)
        if current_state in ('RED', 'GREEN'):
            # Track state transition durations
            prev_state = cursor.execute("""
                SELECT state 
                FROM traffic_light_states 
                WHERE light_id = ? 
                AND timestamp < ?
                ORDER BY timestamp DESC 
                LIMIT 1
            """, (light_id, timestamp)).fetchone()

            if prev_state and prev_state[0] != current_state and prev_state[0] in ('RED', 'GREEN'):
                # Get first timestamp of previous state sequence
                prev_timestamp_result = cursor.execute("""
                    SELECT MIN(timestamp) 
                    FROM traffic_light_states
                    WHERE light_id = ? 
                    AND state = ? 
                    AND timestamp < ?
                    AND timestamp > (
                        SELECT COALESCE(MAX(timestamp), 0) 
                        FROM traffic_light_states 
                        WHERE light_id = ? 
                        AND state != ?
                        AND timestamp < ?
                    )
                """, (light_id, prev_state[0], timestamp, light_id, prev_state[0], timestamp)).fetchone()
                
                # Check if prev_timestamp is None before calculating duration
                if prev_timestamp_result and prev_timestamp_result[0] is not None:
                    prev_timestamp = prev_timestamp_result[0]
                    # Calculate duration from actual state change
                    duration = timestamp - prev_timestamp
            
                    # Only record transitions between valid states (RED and GREEN)
                    cursor.execute("""
                        INSERT OR REPLACE INTO state_durations 
                        (light_id, previous_state, next_state, duration, last_updated)
                        VALUES (?, ?, ?, ?, ?)
                    """, (light_id, prev_state[0], current_state, duration, 
                         datetime.now().isoformat()))
                    
                    print(f"\n[DEBUG] Recorded state transition for light {light_id}:")
                    print(f"  Previous: {prev_state[0]} (started at {datetime.fromtimestamp(prev_timestamp).isoformat()})")
                    print(f"  Current: {current_state} (changed at {datetime.fromtimestamp(timestamp).isoformat()})")
                    print(f"  Duration: {duration:.2f}s")
                    print(f"  Recorded at: {datetime.now().isoformat()}")
                else:
                    print(f"\n[WARNING] Could not determine previous timestamp for light {light_id}")
                    print(f"  Previous state: {prev_state[0]}, Current state: {current_state}")
                    print(f"  No duration recorded")
    
    # Update intersection states cache
    for intersection_id, data in processed['intersections'].items():
        intersection_states[intersection_id] = {
            'overall_state': data['overall_state'],
            'lights': data['lights'],
            'timestamp': datetime.fromtimestamp(timestamp).isoformat()
        }
    
    # Only commit and close if we opened a connection
    if has_valid_states:
        conn.commit()
        conn.close()


def on_message(client, userdata, msg):
    """Handle incoming MQTT messages and process traffic states."""
    try:
        payload_decoded = base64.b64decode(msg.payload)
        telemetry = telemetry_pb2.mqtt_msg_t()
        telemetry.ParseFromString(payload_decoded)

        # Save raw telemetry
        save_telemetry(telemetry.id, telemetry.channels, telemetry.timestamp, telemetry.counter)
        
        # Process traffic light states
        states = process_traffic_states(telemetry.id, telemetry.channels)
        
        # Update intersection states
        for light_id, state in states.items():
            intersection_states[light_id] = {
                **state,
                'timestamp': datetime.fromtimestamp(telemetry.timestamp).isoformat()
            }
        
        # Print status
        print(f"\nNew telemetry received:")
        print(f"  Detector ID: {telemetry.id}")
        print(f"  Timestamp: {datetime.fromtimestamp(telemetry.timestamp).isoformat()}")
        print("  Traffic Light States:")
        
        # Check if any valid states exist
        has_valid_states = False
        for light_id, light_data in states['lights'].items():
            status = "RED" if light_data['red'] else "GREEN" if light_data['green'] else "UNKNOWN"
            print(f"    {light_data['name']} ({light_data['location']}): {status}")
            if status != "UNKNOWN":
                has_valid_states = True
        
        if not has_valid_states:
            print("  WARNING: No valid states detected, telemetry not saved")
            
            # Debug logging for state determination
            print(f"      [DEBUG] Detector: {telemetry.id}, Light ID: {light_id}")
            print(f"      [DEBUG] Red state: {light_data['red']}, Green state: {light_data['green']}")
            print(f"      [DEBUG] Raw channel mask: 0b{format(telemetry.channels, '032b')}")
            # Get channel config for this light
            light_config = get_traffic_light_config(telemetry.id)
            red_masks = [str(c[1]) for c in light_config if c[0] == light_id and c[2] == 'RED']
            green_masks = [str(c[1]) for c in light_config if c[0] == light_id and c[2] == 'GREEN']
            print(f"      [DEBUG] Configured channels - RED: {', '.join(red_masks)}, GREEN: {', '.join(green_masks)}")
        
        # Print raw channel states for debugging
        channel_states = ["ON" if (telemetry.channels & (1 << i)) else "OFF" for i in range(32)]
        print(f"  Raw Channel States: {', '.join(channel_states)}")
    
    except Exception as e:
        print(f"Failed to process message: {e}")
        import traceback
        traceback.print_exc()

def cleanup_old_data():
    """Remove old data to prevent database bloat"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Keep only the last 1 hour of telemetry data
    retention_hours = 1
    cutoff_timestamp = int(time.time()) - (retention_hours * 60 * 60)
    
    cursor.execute("DELETE FROM telemetry WHERE timestamp < ?", (cutoff_timestamp,))
    deleted_telemetry = cursor.rowcount
    
    # Keep only the last hour of state changes
    cursor.execute("""
        DELETE FROM traffic_light_states 
        WHERE timestamp < ?
    """, (cutoff_timestamp,))
    deleted_states = cursor.rowcount
    
    # Remove any invalid state transitions (involving UNKNOWN states)
    cursor.execute("""
        DELETE FROM state_durations
        WHERE previous_state = 'UNKNOWN' OR next_state = 'UNKNOWN'
    """)
    deleted_transitions = cursor.rowcount
    if deleted_transitions > 0:
        print(f"[CLEANUP] Removed {deleted_transitions} invalid state transitions involving UNKNOWN states")
    
    # Commit changes before vacuum
    conn.commit()
    
    # Vacuum database to reclaim space (only if we deleted a significant amount of data)
    if deleted_telemetry > 50 or deleted_states > 50 or deleted_transitions > 0:
        cursor.execute("VACUUM")
        print("[CLEANUP] Database vacuumed to reclaim space")
    
    conn.close()
    
    if deleted_telemetry > 0 or deleted_states > 0:
        print(f"[CLEANUP] Removed {deleted_telemetry} old telemetry records and {deleted_states} old state records")

def initialize_database():
    """Initialize all required database tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create all necessary tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detector_id INTEGER NOT NULL,
            channels INTEGER NOT NULL,
            timestamp INTEGER NOT NULL,
            counter INTEGER NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS detectors (
            name TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS traffic_lights (
            light_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            location TEXT NOT NULL,
            intersection_id TEXT NOT NULL DEFAULT 'UNGROUPED'
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS traffic_light_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            light_id INTEGER NOT NULL,
            detector_id INTEGER NOT NULL,
            channel_mask INTEGER NOT NULL,
            signal_color TEXT CHECK(signal_color IN ('RED', 'GREEN')) NOT NULL,
            FOREIGN KEY (light_id) REFERENCES traffic_lights(light_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS traffic_light_states (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            light_id INTEGER NOT NULL,
            state TEXT CHECK(state IN ('RED', 'GREEN')) NOT NULL,
            timestamp DATETIME NOT NULL,
            FOREIGN KEY (light_id) REFERENCES traffic_lights(light_id)
        )
    """)
    
    # Create indexes for better query performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp ON telemetry(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_traffic_light_states_light_timestamp ON traffic_light_states(light_id, timestamp)")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS state_durations (
            light_id INTEGER NOT NULL,
            previous_state TEXT NOT NULL,
            next_state TEXT NOT NULL,
            duration REAL NOT NULL,
            last_updated DATETIME NOT NULL,
            PRIMARY KEY (light_id, previous_state, next_state),
            FOREIGN KEY (light_id) REFERENCES traffic_lights(light_id)
        )
    """)
    
    conn.commit()
    conn.close()
    print("Database tables initialized")

def main():
    # Initialize database tables
    initialize_database()
    
    # Run initial cleanup
    cleanup_old_data()
    
    username, password = register_detector.get_or_create_user(LISTENER_USERNAME)
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(username, password)
    client.on_message = on_message
    
    # Set up periodic cleanup task
    cleanup_interval = 900  # Run cleanup every 15 minutes
    last_cleanup = time.time()
    
    def on_connect(client, userdata, flags, rc, properties=None):
        print(f"Connected with result code {rc}")
        client.subscribe(MQTT_TOPIC)
    
    def maintenance_loop():
        nonlocal last_cleanup
        current_time = time.time()
        
        # Run cleanup if it's time
        if current_time - last_cleanup > cleanup_interval:
            cleanup_old_data()
            last_cleanup = current_time
            
        # Schedule next check in 5 minutes
        client.loop_timeout = 300
    
    client.on_connect = on_connect
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    
    print("MQTT Listener Started...")
    
    # Main loop with maintenance
    while True:
        client.loop(timeout=60.0)
        maintenance_loop()

if __name__ == "__main__":
    main()
