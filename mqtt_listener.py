import base64
import sqlite3
import register_detector
import time
from collections import defaultdict
from datetime import datetime

import paho.mqtt.client as mqtt
import telemetry_pb2

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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Save raw telemetry
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
            intersection_id TEXT NOT NULL,
            description TEXT NOT NULL
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
    
    cursor.execute("INSERT INTO telemetry (detector_id, channels, timestamp, counter) VALUES (?, ?, ?, ?)",
                   (detector_id, channels, timestamp, counter))
    
    # Process and save traffic states
    processed = process_traffic_states(detector_id, channels)
    
    # Save individual light states
    for light_id, state in processed['lights'].items():
        current_state = 'RED' if state['red'] else 'GREEN'
        cursor.execute("""
            INSERT INTO traffic_light_states (light_id, state, timestamp)
            VALUES (?, ?, ?)
        """, (light_id, current_state, timestamp))

        # Track state transition durations
        prev_state = cursor.execute("""
            SELECT state 
            FROM traffic_light_states 
            WHERE light_id = ? 
            AND timestamp < ?
            ORDER BY timestamp DESC 
            LIMIT 1
        """, (light_id, timestamp)).fetchone()

        if prev_state and prev_state[0] != current_state:
            # Get first timestamp of previous state sequence
            prev_timestamp = cursor.execute("""
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
            """, (light_id, prev_state[0], timestamp, light_id, prev_state[0], timestamp)).fetchone()[0]
            
            # Calculate duration from actual state change
            duration = timestamp - prev_timestamp
            
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
    
    # Update intersection states cache
    for intersection_id, data in processed['intersections'].items():
        intersection_states[intersection_id] = {
            'overall_state': data['overall_state'],
            'lights': data['lights'],
            'timestamp': datetime.fromtimestamp(timestamp).isoformat()
        }
    
    conn.commit()
    conn.close()

def predict_next_change(light_id, current_state):
    """Enhanced prediction with time-weighted averages"""
    print(f"\n[PREDICT] Starting prediction for light {light_id} ({current_state})")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT previous_state, next_state, 
               SUM(duration * weight)/SUM(weight) as weighted_avg,
               COUNT(*) as samples
        FROM (
            SELECT *, 
                   EXP(-0.001 * (strftime('%s','now') - last_updated)) as weight
            FROM state_durations
            WHERE light_id = ? AND previous_state = ?
            ORDER BY last_updated DESC
            LIMIT 100
        )
        GROUP BY previous_state, next_state
        HAVING samples >= 3  # More clear minimum sample threshold
    ''', (light_id, current_state))
    
    history = cursor.fetchall()
    print(f"[PREDICT] Raw SQL results: {history}")
    
    # Get current state duration
    cursor.execute('''
        SELECT timestamp 
        FROM traffic_light_states 
        WHERE light_id = ? 
        ORDER BY timestamp DESC 
        LIMIT 1
    ''', (light_id,))
    result = cursor.fetchone()
    current_state_start = result['timestamp'] if result else time.time()
    current_state_duration = time.time() - current_state_start
    
    if history:
        best = max(history, key=lambda x: x['samples'])
        avg_duration = max(min(best['weighted_avg'], 300), 30)  # Safety limits
        time_remaining = avg_duration - current_state_duration
        confidence = min(best['samples'] / 10, 1.0)
        
        print(f"[PREDICT] Using historical data:")
        print(f"  Best transition: {best['previous_state']}->{best['next_state']}")
        print(f"  Samples: {best['samples']}, Weighted avg: {best['weighted_avg']:.2f}s")
        print(f"  Current duration: {current_state_duration:.2f}s")
        print(f"  Time remaining: {time_remaining:.2f}s, Confidence: {confidence:.2f}")
        
        return (best['next_state'], max(0, time_remaining), confidence)
    
    # Fallback to time-aware defaults
    hour = datetime.now().hour
    if 7 <= hour < 10 or 16 <= hour < 19:  # Rush hours
        default_duration = 40 if current_state == 'GREEN' else 90
    else:
        default_duration = 60 if current_state == 'GREEN' else 120
    
    print(f"[PREDICT] Using fallback defaults:")
    print(f"  Current hour: {hour}, Rush hours: {7 <= hour < 10 or 16 <= hour < 19}")
    print(f"  Default duration: {default_duration}s for {current_state}")
    print(f"  Current state duration: {current_state_duration:.2f}s")
        
    return ('RED' if current_state == 'GREEN' else 'GREEN', 
           max(default_duration - current_state_duration, 0),
           0.5)

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
        for light_id, light_data in states['lights'].items():
            status = "RED" if light_data['red'] else "GREEN" if light_data['green'] else "UNKNOWN"
            print(f"    {light_data['name']} ({light_data['location']}): {status}")
            
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

def main():
    username, password = register_detector.get_or_create_user(LISTENER_USERNAME)
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(username, password)
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.subscribe(MQTT_TOPIC)

    print("MQTT Listener Started...")
    client.loop_forever()

if __name__ == "__main__":
    main()
