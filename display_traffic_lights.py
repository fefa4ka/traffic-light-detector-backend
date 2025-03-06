import sqlite3

DB_PATH = "/data/detectors.db"

def display_traffic_lights():
    """Retrieve and display all set up traffic lights and their channel mappings."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT tl.light_id, tl.name, tl.location, tlc.detector_id, tlc.channel_mask, tlc.signal_color
        FROM traffic_lights tl
        JOIN traffic_light_channels tlc ON tl.light_id = tlc.light_id
        ORDER BY tl.light_id, tlc.signal_color
    """)

    traffic_lights = cursor.fetchall()
    conn.close()

    if not traffic_lights:
        print("No traffic lights found.")
        return

    print("Configured Traffic Lights:")
    current_id = None
    for light_id, name, location, detector_id, channel_mask, signal_color in traffic_lights:
        if light_id != current_id:
            print(f"\nTraffic Light ID: {light_id}")
            print(f"  Name: {name}")
            print(f"  Location: {location}")
            current_id = light_id
        print(f"  Detector ID: {detector_id}")
        print(f"  {signal_color} Signal - Channel: {channel_mask}")

if __name__ == "__main__":
    display_traffic_lights()
