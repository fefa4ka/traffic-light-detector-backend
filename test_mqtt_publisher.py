import time
import base64
import paho.mqtt.client as mqtt
import telemetry_pb2  # Import generated protobuf module

MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "$me/device/state"
DETECTOR_ID = 1
USERNAME = "test_detector"
PASSWORD = "test_password"

def generate_mock_data():
    """Generate mock telemetry data"""
    telemetry = telemetry_pb2.mqtt_msg_t()
    telemetry.id = DETECTOR_ID
    telemetry.channels = 3  # Example bitmask (e.g., Red + Green active)
    telemetry.timestamp = int(time.time())
    telemetry.counter = 1

    return base64.b64encode(telemetry.SerializeToString()).decode()

def main():
    client = mqtt.Client()
    client.username_pw_set(USERNAME, PASSWORD)
    client.connect(MQTT_BROKER, MQTT_PORT, 60)

    while True:
        payload = generate_mock_data()
        client.publish(MQTT_TOPIC, payload)
        print(f"Published mock data: {payload}")
        time.sleep(5)  # Send data every 5 seconds

if __name__ == "__main__":
    main()
