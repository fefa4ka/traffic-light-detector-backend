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
    
    # Always open a connection, but only save telemetry if we have valid states
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Only save telemetry if we have valid states
        if has_valid_states:
            cursor.execute("INSERT INTO telemetry (detector_id, channels, timestamp, counter) VALUES (?, ?, ?, ?)",
                       (detector_id, channels, timestamp, counter))
        
        # Save individual light states
        for light_id, state in processed['lights'].items():
            # Only save states that are explicitly RED or GREEN
            current_state = "UNKNOWN"
            if state['red']:
                current_state = 'RED'
            elif state['green']:
                current_state = 'GREEN'
            
            # Only proceed if we have a valid state
            if current_state in ('RED', 'GREEN'):
                # Get the previous state record for this light
                prev_state_record = cursor.execute("""
                    SELECT state, timestamp 
                    FROM traffic_light_states 
                    WHERE light_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT 1
                """, (light_id,)).fetchone()
                
                # Insert the new state
                cursor.execute("""
                    INSERT INTO traffic_light_states (light_id, state, timestamp)
                    VALUES (?, ?, ?)
                """, (light_id, current_state, timestamp))
                
                # Check if this is a state transition
                if prev_state_record and prev_state_record[0] != current_state and prev_state_record[0] in ('RED', 'GREEN'):
                    prev_state = prev_state_record[0]
                    prev_timestamp = prev_state_record[1]
                    
                    # Calculate duration - ensure timestamps are numeric
                    try:
                        if isinstance(prev_timestamp, str) and not prev_timestamp.isdigit():
                            # Try to parse ISO format
                            from datetime import datetime
                            prev_dt = datetime.fromisoformat(prev_timestamp)
                            prev_timestamp = int(prev_dt.timestamp())
                        else:
                            prev_timestamp = int(float(prev_timestamp))
                            
                        # Ensure current timestamp is numeric
                        if isinstance(timestamp, str) and not timestamp.isdigit():
                            current_dt = datetime.fromisoformat(timestamp)
                            timestamp = int(current_dt.timestamp())
                        else:
                            timestamp = int(float(timestamp))
                            
                        # Calculate duration
                        duration = timestamp - prev_timestamp
                
                        # Only record transitions if duration is reasonable (between 5 and 300 seconds)
                        if 5 <= duration <= 300:
                            cursor.execute("""
                                INSERT OR REPLACE INTO state_durations 
                                (light_id, previous_state, next_state, duration, last_updated)
                                VALUES (?, ?, ?, ?, ?)
                            """, (light_id, prev_state, current_state, duration, 
                                 datetime.now().isoformat()))
                            
                            print(f"\n[DEBUG] Recorded state transition for light {light_id}:")
                            print(f"  Previous: {prev_state} (started at {datetime.fromtimestamp(prev_timestamp).isoformat()})")
                            print(f"  Current: {current_state} (changed at {datetime.fromtimestamp(timestamp).isoformat()})")
                            print(f"  Duration: {duration:.2f}s")
                            print(f"  Recorded at: {datetime.now().isoformat()}")
                        else:
                            print(f"\n[WARNING] Unreasonable duration ({duration:.2f}s) for light {light_id}")
                            print(f"  Previous: {prev_state} at {prev_timestamp}")
                            print(f"  Current: {current_state} at {timestamp}")
                            print(f"  Duration outside valid range (5-300s), not recording")
                    except (ValueError, TypeError) as e:
                        print(f"\n[WARNING] Error calculating duration for light {light_id}: {e}")
                        print(f"  Previous state: {prev_state} at {prev_timestamp} (type: {type(prev_timestamp).__name__})")
                        print(f"  Current state: {current_state} at {timestamp} (type: {type(timestamp).__name__})")
                        
                        # Try to fix the timestamp issue by creating a new record with current time
                        try:
                            current_time = int(time.time())
                            cursor.execute("""
                                UPDATE traffic_light_states
                                SET timestamp = ?
                                WHERE light_id = ? AND state = ?
                                ORDER BY rowid DESC
                                LIMIT 1
                            """, (current_time, light_id, current_state))
                            print(f"  Fixed timestamp for latest {current_state} state to {current_time}")
                        except Exception as fix_error:
                            print(f"  Failed to fix timestamp: {fix_error}")
        
        # Update intersection states cache
        for intersection_id, data in processed['intersections'].items():
            intersection_states[intersection_id] = {
                'overall_state': data['overall_state'],
                'lights': data['lights'],
                'timestamp': datetime.now().isoformat()
            }
        
        # Always commit changes
        conn.commit()
    
    except Exception as e:
        print(f"Error saving telemetry data: {e}")
        conn.rollback()
        import traceback
        traceback.print_exc()
    
    finally:
        # Always close the connection
        conn.close()


def on_message(client, userdata, msg):
    """Handle incoming MQTT messages and process traffic states."""
    try:
        payload_decoded = base64.b64decode(msg.payload)
        telemetry = telemetry_pb2.mqtt_msg_t()
        telemetry.ParseFromString(payload_decoded)

        # Save raw telemetry
        save_telemetry(telemetry.id, telemetry.channels, time.time(), telemetry.counter)
        
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
    
    print("[CLEANUP] Starting database maintenance...")
    current_time = int(time.time())
    
    try:
        # Keep only the last 1 hour of telemetry data
        retention_hours = 1
        cutoff_timestamp = current_time - (retention_hours * 60 * 60)
        
        cursor.execute("DELETE FROM telemetry WHERE timestamp < ?", (cutoff_timestamp,))
        deleted_telemetry = cursor.rowcount
        
        # Keep only the last hour of state changes, but preserve the most recent state for each light
        cursor.execute("""
            DELETE FROM traffic_light_states 
            WHERE timestamp < ? AND rowid NOT IN (
                SELECT MAX(rowid) FROM traffic_light_states GROUP BY light_id, state
            )
        """, (cutoff_timestamp,))
        deleted_states = cursor.rowcount
        
        # Fix any timestamps from before 2024 (likely incorrect)
        year_2024_timestamp = 1704067200  # Jan 1, 2024
        
        # First, identify lights with outdated timestamps
        cursor.execute("""
            SELECT DISTINCT light_id FROM traffic_light_states
            WHERE timestamp < ?
        """, (year_2024_timestamp,))
        
        lights_with_old_timestamps = [row[0] for row in cursor.fetchall()]
        
        if lights_with_old_timestamps:
            print(f"[CLEANUP] Found {len(lights_with_old_timestamps)} lights with outdated timestamps")
            
            # For each light with outdated timestamps, keep only the most recent state
            # and update its timestamp to current time
            for light_id in lights_with_old_timestamps:
                # Get the most recent state for this light
                cursor.execute("""
                    SELECT state FROM traffic_light_states
                    WHERE light_id = ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (light_id,))
                
                result = cursor.fetchone()
                if result:
                    current_state = result[0]
                    
                    # Delete all outdated records for this light
                    cursor.execute("""
                        DELETE FROM traffic_light_states
                        WHERE light_id = ?
                    """, (light_id,))
                    
                    # Create a new record with current timestamp
                    cursor.execute("""
                        INSERT INTO traffic_light_states (light_id, state, timestamp)
                        VALUES (?, ?, ?)
                    """, (light_id, current_state, current_time))
                    
                    print(f"[CLEANUP] Reset timestamp for light {light_id} to current time with state {current_state}")
        
        # Remove any invalid state transitions (involving UNKNOWN states)
        cursor.execute("""
            DELETE FROM state_durations
            WHERE previous_state = 'UNKNOWN' OR next_state = 'UNKNOWN'
        """)
        deleted_transitions = cursor.rowcount
        if deleted_transitions > 0:
            print(f"[CLEANUP] Removed {deleted_transitions} invalid state transitions")
        
        # Update outdated state_durations records
        cursor.execute("""
            UPDATE state_durations
            SET last_updated = ?
            WHERE last_updated < ?
        """, (datetime.now().isoformat(), datetime.now().replace(year=datetime.now().year-1).isoformat()))
        
        updated_durations = cursor.rowcount
        if updated_durations > 0:
            print(f"[CLEANUP] Updated timestamps for {updated_durations} duration records")
        
        # Commit changes before vacuum
        conn.commit()
        
        # Vacuum database to reclaim space (only if we deleted a significant amount of data)
        if deleted_telemetry > 50 or deleted_states > 50 or deleted_transitions > 0 or lights_with_old_timestamps:
            cursor.execute("VACUUM")
            print("[CLEANUP] Database vacuumed to reclaim space")
        
        print(f"[CLEANUP] Maintenance complete: Removed {deleted_telemetry} telemetry records, {deleted_states} state records")
        
    except Exception as e:
        print(f"[CLEANUP] Error during database maintenance: {e}")
        conn.rollback()
        import traceback
        traceback.print_exc()
    
    finally:
        conn.close()

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
