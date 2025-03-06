import sqlite3

DB_PATH = "/data/detectors.db"

def interactive_input(prompt):
    """Helper function to get user input with validation."""
    while True:
        value = input(prompt).strip()
        if value:
            return value

def setup_traffic_light():
    """Interactive setup for a traffic light and its channel mappings."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS traffic_lights (
            light_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            location TEXT NOT NULL
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

    name = interactive_input("Enter traffic light name: ")
    location = interactive_input("Enter traffic light location: ")
    detector_id = interactive_input("Enter detector ID: ")

    cursor.execute("INSERT INTO traffic_lights (name, location) VALUES (?, ?)", (name, location))
    light_id = cursor.lastrowid

    red_channel = interactive_input("Enter channel number for RED signal: ")
    green_channel = interactive_input("Enter channel number for GREEN signal: ")

    cursor.execute("INSERT INTO traffic_light_channels (light_id, detector_id, channel_mask, signal_color) VALUES (?, ?, ?, ?)",
                   (light_id, detector_id, red_channel, "RED"))

    cursor.execute("INSERT INTO traffic_light_channels (light_id, detector_id, channel_mask, signal_color) VALUES (?, ?, ?, ?)",
                   (light_id, detector_id, green_channel, "GREEN"))

    conn.commit()
    conn.close()

    print(f"Traffic light '{name}' configured successfully.")

if __name__ == "__main__":
    setup_traffic_light()
