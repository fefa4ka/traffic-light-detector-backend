import base64
import sqlite3
import register_detector  # Import detector registration module

import paho.mqtt.client as mqtt
import telemetry_pb2  # Import generated protobuf module

DB_PATH = "/data/detectors.db"
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "$me/device/state"
LISTENER_USERNAME = "listener"

def save_telemetry(detector_id, channels, timestamp, counter):
    """Save telemetry data into the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
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
    conn.commit()
    conn.close()

def on_message(client, userdata, msg):
    """Handle incoming MQTT messages."""
    try:
        payload_decoded = base64.b64decode(msg.payload)
        telemetry = telemetry_pb2.mqtt_msg_t()
        telemetry.ParseFromString(payload_decoded)

        save_telemetry(telemetry.id, telemetry.channels, telemetry.timestamp, telemetry.counter)
        print(f"Stored telemetry: ID={telemetry.id}, Timestamp={telemetry.timestamp}, Counter={telemetry.counter}")
        
        # Decode channels bitmask and print the state of each channel in a single line
        channel_states = ["ON" if (telemetry.channels & (1 << i)) else "OFF" for i in range(32)]
        print(f"  Channel States: {', '.join(channel_states)}")
    
    except Exception as e:
        print(f"Failed to process message: {e}")

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
