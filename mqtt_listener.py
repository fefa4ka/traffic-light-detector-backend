import base64
import sqlite3
import register_detector
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
        
        # Update signal state
        if signal_color == 'RED':
            states[light_id]['red'] = is_active
        elif signal_color == 'GREEN':
            states[light_id]['green'] = is_active
            
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
        CREATE TABLE IF NOT EXISTS traffic_light_states (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            light_id INTEGER NOT NULL,
            state TEXT CHECK(state IN ('RED', 'GREEN')) NOT NULL,
            timestamp DATETIME NOT NULL,
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
    
    # Update intersection states cache
    for intersection_id, data in processed['intersections'].items():
        intersection_states[intersection_id] = {
            'overall_state': data['overall_state'],
            'lights': data['lights'],
            'timestamp': datetime.fromtimestamp(timestamp).isoformat()
        }
    
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
        for light_id, state in states.items():
            status = "RED" if state['red'] else "GREEN" if state['green'] else "UNKNOWN"
            print(f"    {state['name']} ({state['location']}): {status}")
        
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
