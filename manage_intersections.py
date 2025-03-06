import sqlite3
from datetime import datetime

DB_PATH = "/data/detectors.db"

def display_all_traffic_lights():
    """Display all traffic lights with their current intersection grouping."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT light_id, name, location, intersection_id 
        FROM traffic_lights
        ORDER BY intersection_id, light_id
    """)
    
    lights = cursor.fetchall()
    conn.close()
    
    if not lights:
        print("No traffic lights found in database.")
        return
    
    current_intersection = None
    for light_id, name, location, intersection_id in lights:
        if intersection_id != current_intersection:
            print(f"\nIntersection Group: {intersection_id or 'Ungrouped'}")
            current_intersection = intersection_id
        print(f"  ID: {light_id} | Name: {name} | Location: {location}")

def validate_light_ids(light_ids):
    """Check if provided light IDs exist in the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    placeholders = ','.join(['?'] * len(light_ids))
    cursor.execute(f"""
        SELECT light_id FROM traffic_lights
        WHERE light_id IN ({placeholders})
    """, light_ids)
    
    valid_ids = {row[0] for row in cursor.fetchall()}
    conn.close()
    
    return len(valid_ids) == len(light_ids), valid_ids

def create_intersection_group():
    """Interactive interface for creating/updating intersection groups."""
    print("\nExisting Traffic Lights:")
    display_all_traffic_lights()
    
    # Get intersection metadata
    intersection_name = input("\nEnter intersection name: ").strip()
    intersection_location = input("Enter intersection location: ").strip()
    intersection_id = f"{intersection_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M')}"
    
    # Get traffic light IDs
    while True:
        id_input = input("\nEnter traffic light IDs to include (comma-separated): ").strip()
        if not id_input:
            print("Please enter at least one traffic light ID.")
            continue
            
        try:
            light_ids = [int(id.strip()) for id in id_input.split(',')]
        except ValueError:
            print("Invalid input. Please enter numeric IDs separated by commas.")
            continue
            
        valid, valid_ids = validate_light_ids(light_ids)
        if not valid:
            invalid_ids = set(light_ids) - valid_ids
            print(f"Invalid IDs found: {', '.join(map(str, invalid_ids))}")
            continue
            
        break
    
    # Update database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Update selected lights with new intersection ID
        placeholders = ','.join(['?'] * len(light_ids))
        cursor.execute(f"""
            UPDATE traffic_lights
            SET intersection_id = ?
            WHERE light_id IN ({placeholders})
        """, (intersection_id, *light_ids))
        
        conn.commit()
        print(f"\nSuccessfully created intersection group '{intersection_id}'")
        print(f"Contains {len(light_ids)} traffic lights")
        
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Database error: {str(e)}")
    finally:
        conn.close()

if __name__ == "__main__":
    create_intersection_group()
