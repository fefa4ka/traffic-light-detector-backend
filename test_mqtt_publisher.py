import base64
import random
import sqlite3
import time

import paho.mqtt.client as mqtt
import telemetry_pb2  # Import generated protobuf module

import register_detector  # Import detector registration module

DB_PATH = "/data/detectors.db"
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "$me/device/state"
DETECTOR_ID = 1


counter = 0

def generate_mock_data():
    """Generate mock telemetry data"""
    global counter
    telemetry = telemetry_pb2.mqtt_msg_t()
    telemetry.id = DETECTOR_ID
    telemetry.channels = random.randint(1, 2**31 - 1)  # Random bitmask for 32 channels
    telemetry.timestamp = int(time.time())
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
