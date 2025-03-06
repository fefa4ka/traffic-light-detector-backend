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

def get_traffic_light_config(detector_id):
    """Get traffic light configuration for a detector."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT tlc.light_id, tlc.channel_mask, tlc.signal_color, tl.name, tl.location
        FROM traffic_light_channels tlc
        JOIN traffic_lights tl ON tlc.light_id = tl.light_id
        WHERE tlc.detector_id = ?
    """, (detector_id,))
    
    config = cursor.fetchall()
    conn.close()
    return config

def process_traffic_states(detector_id, channels):
    """Process raw channels into traffic light states."""
    config = get_traffic_light_config(detector_id)
    states = {}
    
    for light_id, channel_mask, signal_color, name, location in config:
        if light_id not in states:
            states[light_id] = {
                'name': name,
                'location': location,
                'red': False,
                'green': False
            }
        
        if channels & channel_mask:
            states[light_id]['red'] = signal_color == 'RED'
            states[light_id]['green'] = signal_color == 'GREEN'
    
    return states

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
    
    cursor.execute("INSERT INTO telemetry (detector_id, channels, timestamp, counter) VALUES (?, ?, ?, ?)",
                   (detector_id, channels, timestamp, counter))
    
    # Process and save traffic states
    states = process_traffic_states(detector_id, channels)
    for light_id, state in states.items():
        cursor.execute("""
            INSERT INTO traffic_states (light_id, red_state, green_state, timestamp)
            VALUES (?, ?, ?, ?)
        """, (light_id, state['red'], state['green'], timestamp))
    
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
