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
        # Create Office intersection light
        office_light = {
            'name': 'Office Main Entrance',
            'location': '55.754052, 37.620482',
            'intersection_id': 'Office',
            'red_channel': 1,
            'green_channel': 0
        }

        # Insert traffic light
        cursor.execute("""
            INSERT INTO traffic_lights (name, location, intersection_id)
            VALUES (?, ?, ?)
        """, (office_light['name'], office_light['location'], office_light['intersection_id']))
        light_id = cursor.lastrowid
        
        # Insert RED channel mapping (channel 1)
        cursor.execute("""
            INSERT INTO traffic_light_channels (light_id, detector_id, channel_mask, signal_color)
            VALUES (?, ?, ?, ?)
        """, (light_id, 1761, 1 << office_light['red_channel'], 'RED'))
        
        # Insert GREEN channel mapping (channel 0)
        cursor.execute("""
            INSERT INTO traffic_light_channels (light_id, detector_id, channel_mask, signal_color)
            VALUES (?, ?, ?, ?)
        """, (light_id, 1761, 1 << office_light['green_channel'], 'GREEN'))

        conn.commit()
        print("Successfully loaded production fixtures:")
        print(f"  Intersection: {office_light['intersection_id']}")
        print(f"  Light: {office_light['name']}")
        print(f"    RED: channel {office_light['red_channel']}")
        print(f"    GREEN: channel {office_light['green_channel']}")
        print(f"  Detector ID: 1761")

    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error loading production fixtures: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    load_prod_fixtures()
