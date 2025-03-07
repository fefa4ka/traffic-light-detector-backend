import base64
import random
import sqlite3
import time
from collections import defaultdict

import paho.mqtt.client as mqtt
import telemetry_pb2  # Import generated protobuf module

import register_detector  # Import detector registration module

DB_PATH = "/data/detectors.db"
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "$me/device/state"
DETECTOR_ID = 1


counter = 0

def get_channel_mappings():
    """Get channel mappings from database based on fixtures"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT tlc.channel_mask, tlc.signal_color, tl.light_id
        FROM traffic_light_channels tlc
        JOIN traffic_lights tl ON tlc.light_id = tl.light_id
        WHERE tlc.detector_id = ?
    """, (DETECTOR_ID,))
    mappings = cursor.fetchall()
    conn.close()
    
    # Organize by light ID and signal color
    config = defaultdict(dict)
    for channel_mask, signal_color, light_id in mappings:
        config[light_id][signal_color] = channel_mask
    return config

# Track light states and their timing
light_states = defaultdict(lambda: {'state': 'RED', 'last_change': time.time()})
STATE_DURATION = 30  # Seconds between state changes

def generate_mock_data():
    """Generate telemetry data following fixture-defined patterns"""
    global counter
    telemetry = telemetry_pb2.mqtt_msg_t()
    telemetry.id = DETECTOR_ID
    channels = 0
    config = get_channel_mappings()
    
    current_time = time.time()
    
    # Update states based on timing
    for light_id in config:
        state_info = light_states[light_id]
        if current_time - state_info['last_change'] > STATE_DURATION:
            # Toggle state
            new_state = 'GREEN' if state_info['state'] == 'RED' else 'RED'
            light_states[light_id] = {
                'state': new_state,
                'last_change': current_time
            }
    
    # Set channels based on current states
    for light_id, signals in config.items():
        current_state = light_states[light_id]['state']
        channels |= signals[current_state]
    
    telemetry.channels = channels
    telemetry.timestamp = int(current_time)
    counter += 1
    telemetry.counter = counter

    return base64.b64encode(telemetry.SerializeToString()).decode()

USERNAME, PASSWORD = register_detector.get_or_create_user(DETECTOR_ID)

def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(USERNAME, PASSWORD)
    client.connect(MQTT_BROKER, MQTT_PORT, 60)

    while True:
        payload = generate_mock_data()
        client.publish(MQTT_TOPIC, payload)
        print(f"Published mock data: {payload}")
        time.sleep(5)  # Send data every 5 seconds

if __name__ == "__main__":
    main()
