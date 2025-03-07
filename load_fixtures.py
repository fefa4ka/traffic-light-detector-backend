import sqlite3
from datetime import datetime

DB_PATH = "/data/detectors.db"

def load_fixtures():
    """Load test fixtures with 4 traffic lights in an intersection for detector 1"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create required tables
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
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS detectors (
            name TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    """)
    
    # Create intersection
    intersection_id = f"Downtown_Crossing_{datetime.now().strftime('%Y%m%d%H%M')}"
    
    # Traffic light configurations
    lights = [
        {
            'name': 'Red Square Northbound',
            'location': '55.753930, 37.620795',  # Red Square coordinates
            'red_channel': 0,
            'green_channel': 1
        },
        {
            'name': 'Tverskaya Southbound', 
            'location': '55.764937, 37.605676',  # Tverskaya Street coordinates
            'red_channel': 2,
            'green_channel': 3
        },
        {
            'name': 'Kremlin Eastbound',
            'location': '55.751999, 37.617734',  # Kremlin coordinates
            'red_channel': 4,
            'green_channel': 5
        },
        {
            'name': 'Arbat Westbound',
            'location': '55.750446, 37.591615',  # Arbat Street coordinates
            'red_channel': 6, 
            'green_channel': 7
        }
    ]
    
    try:
        # Insert traffic lights and channel mappings
        for light in lights:
            # Insert traffic light
            cursor.execute("""
                INSERT INTO traffic_lights (name, location, intersection_id)
                VALUES (?, ?, ?)
            """, (light['name'], light['location'], intersection_id))
            light_id = cursor.lastrowid
            
            # Insert RED channel mapping
            cursor.execute("""
                INSERT INTO traffic_light_channels (light_id, detector_id, channel_mask, signal_color)
                VALUES (?, ?, ?, ?)
            """, (light_id, 1, 1 << light['red_channel'], 'RED'))
            
            # Insert GREEN channel mapping
            cursor.execute("""
                INSERT INTO traffic_light_channels (light_id, detector_id, channel_mask, signal_color)
                VALUES (?, ?, ?, ?)
            """, (light_id, 1, 1 << light['green_channel'], 'GREEN'))
        
        conn.commit()
        print(f"Successfully loaded fixtures for detector 1")
        print(f"Created intersection: {intersection_id}")
        print("Configured 4 traffic lights with channel mappings:")
        for i, light in enumerate(lights, 1):
            print(f"  Light {i}: {light['name']}")
            print(f"    RED: channel {light['red_channel']}, GREEN: channel {light['green_channel']}")
            
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error loading fixtures: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    load_fixtures()
