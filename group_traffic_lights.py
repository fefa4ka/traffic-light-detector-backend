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
            location TEXT NOT NULL,
            intersection_id TEXT NOT NULL DEFAULT 'UNGROUPED'
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

    # Get and validate channel numbers
    red_channel = int(interactive_input("Enter channel number (0-31) for RED signal: "))
    green_channel = int(interactive_input("Enter channel number (0-31) for GREEN signal: "))
    
    if red_channel == green_channel:
        raise ValueError("RED and GREEN cannot use the same channel number")
    if not (0 <= red_channel <= 31) or not (0 <= green_channel <= 31):
        raise ValueError("Channel numbers must be between 0-31")

    # Convert to bitmasks
    red_mask = 1 << red_channel
    green_mask = 1 << green_channel

    cursor.execute("INSERT INTO traffic_light_channels (light_id, detector_id, channel_mask, signal_color) VALUES (?, ?, ?, ?)",
                   (light_id, detector_id, red_mask, "RED"))

    cursor.execute("INSERT INTO traffic_light_channels (light_id, detector_id, channel_mask, signal_color) VALUES (?, ?, ?, ?)",
                   (light_id, detector_id, green_mask, "GREEN"))

    conn.commit()
    conn.close()

    print(f"Traffic light '{name}' configured successfully.")

if __name__ == "__main__":
    setup_traffic_light()
