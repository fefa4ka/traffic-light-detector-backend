import sqlite3
from datetime import datetime

DB_PATH = "/data/detectors.db"

def load_prod_fixtures():
    """Load production fixtures for Office intersection with detector 1761"""
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
    
    try:
        # Define the intersection and traffic lights
        intersection_id = 'Office'
        detector_id = 1761
        location = '55.754052, 37.620482'
        
        # Define all 4 traffic lights with their channels
        traffic_lights = [
            {
                'name': 'Office Light 1',
                'location': location,
                'intersection_id': intersection_id,
                'red_channel': 0,
                'green_channel': 4
            },
            {
                'name': 'Office Light 2',
                'location': location,
                'intersection_id': intersection_id,
                'red_channel': 1,
                'green_channel': 5
            },
            {
                'name': 'Office Light 3',
                'location': location,
                'intersection_id': intersection_id,
                'red_channel': 8,
                'green_channel': 12
            },
            {
                'name': 'Office Light 4',
                'location': location,
                'intersection_id': intersection_id,
                'red_channel': 9,
                'green_channel': 13
            }
        ]
        
        print("Loading production fixtures:")
        
        # Insert all traffic lights
        for light in traffic_lights:
            # Insert traffic light
            cursor.execute("""
                INSERT INTO traffic_lights (name, location, intersection_id)
                VALUES (?, ?, ?)
            """, (light['name'], light['location'], light['intersection_id']))
            light_id = cursor.lastrowid
            
            # Insert RED channel mapping
            cursor.execute("""
                INSERT INTO traffic_light_channels (light_id, detector_id, channel_mask, signal_color)
                VALUES (?, ?, ?, ?)
            """, (light_id, detector_id, 1 << light['red_channel'], 'RED'))
            
            # Insert GREEN channel mapping
            cursor.execute("""
                INSERT INTO traffic_light_channels (light_id, detector_id, channel_mask, signal_color)
                VALUES (?, ?, ?, ?)
            """, (light_id, detector_id, 1 << light['green_channel'], 'GREEN'))
            
            print(f"  Light: {light['name']}")
            print(f"    RED: channel {light['red_channel']}")
            print(f"    GREEN: channel {light['green_channel']}")
        
        conn.commit()
        print(f"Successfully loaded all traffic lights for intersection: {intersection_id}")
        print(f"Detector ID: {detector_id}")

    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error loading production fixtures: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    load_prod_fixtures()
