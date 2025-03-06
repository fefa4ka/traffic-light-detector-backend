import sqlite3
from typing import Dict, List

DB_PATH = "/data/detectors.db"

def display_intersections():
    """Display all intersections with their associated traffic lights."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all unique intersections
    cursor.execute("""
        SELECT DISTINCT intersection_id 
        FROM traffic_lights 
        WHERE intersection_id != 'UNGROUPED'
        ORDER BY intersection_id
    """)
    
    intersections = [row[0] for row in cursor.fetchall()]
    
    # Get all traffic lights grouped by intersection
    cursor.execute("""
        SELECT light_id, name, location, intersection_id 
        FROM traffic_lights
        ORDER BY intersection_id, light_id
    """)
    
    all_lights = cursor.fetchall()
    conn.close()
    
    print("\nConfigured Intersections:")
    if not intersections and not all_lights:
        print("  No intersections or traffic lights found")
        return
    
    # Group lights by intersection
    grouped: Dict[str, List] = {}
    ungrouped = []
    
    for light_id, name, location, intersection_id in all_lights:
        if intersection_id == 'UNGROUPED':
            ungrouped.append((light_id, name, location))
        else:
            grouped.setdefault(intersection_id, []).append((light_id, name, location))
    
    # Print grouped intersections
    for intersection_id in intersections:
        lights = grouped.get(intersection_id, [])
        print(f"\nIntersection: {intersection_id}")
        print(f"  Contains {len(lights)} traffic lights:")
        for light_id, name, location in lights:
            print(f"    ID: {light_id} | Name: {name} | Location: {location}")
    
    # Print ungrouped lights
    if ungrouped:
        print("\nUngrouped Traffic Lights:")
        for light_id, name, location in ungrouped:
            print(f"  ID: {light_id} | Name: {name} | Location: {location}")

if __name__ == "__main__":
    display_intersections()
