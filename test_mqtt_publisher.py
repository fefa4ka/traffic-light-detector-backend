import time
import base64
import random
import sqlite3
import paho.mqtt.client as mqtt
import telemetry_pb2  # Import generated protobuf module
import register_detector  # Import detector registration module

DB_PATH = "/data/detectors.db"
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "$me/device/state"
DETECTOR_ID = 1

def get_or_create_user(detector_id):
    """Retrieve stored credentials or create new ones if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT name, password FROM detectors WHERE name=?", (f"detector_{detector_id}",))
    result = cursor.fetchone()

    if result:
        conn.close()
        return result[0], result[1]

    # If not found, create a new user
    name = f"detector_{detector_id}"
    password = register_detector.generate_password()
    register_detector.create_mqtt_user(name, password)
    register_detector.save_to_db(name, password)

    conn.close()
    return name, password

counter = 0

def generate_mock_data():
    """Generate mock telemetry data"""
    global counter
    telemetry = telemetry_pb2.mqtt_msg_t()
    telemetry.id = DETECTOR_ID
    telemetry.channels = random.randint(1, 2**32 - 1)  # Random bitmask for 32 channels
    telemetry.timestamp = int(time.time())
    counter += 1
    telemetry.counter = counter

    return base64.b64encode(telemetry.SerializeToString()).decode()

USERNAME, PASSWORD = get_or_create_user(DETECTOR_ID)

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
