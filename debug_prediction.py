import sqlite3
from datetime import datetime

DB_PATH = "/data/detectors.db"

def debug_prediction_query():
    """Interactive debugger for traffic light state prediction"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("Traffic Light Prediction Debugger\n" + "="*30)
    
    # Get and validate input parameters
    while True:
        try:
            light_id = int(input("Enter light_id to test: "))
            if light_id <= 0:
                print("Light ID must be a positive integer")
                continue
            break
        except ValueError:
            print("Please enter a valid integer for light_id")

    while True:
        current_state = input("Enter current_state (RED/GREEN): ").strip().upper()
        if current_state in ('RED', 'GREEN'):
            break
        print("State must be either RED or GREEN")
    
    print("\n[1] Checking state_durations table exists...")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='state_durations'")
    table_exists = cursor.fetchone()
    print(f"  Table exists: {'Yes' if table_exists else 'No'}")
    
    if not table_exists:
        print("  Error: state_durations table does not exist!")
        conn.close()
        return
    
    print("\n[2] Getting last transition...")
    cursor.execute("""
        SELECT previous_state, next_state, duration, last_updated
        FROM state_durations
        WHERE light_id = ?
        ORDER BY last_updated DESC
        LIMIT 1
    """, (light_id,))
    
    last_transition = cursor.fetchone()
    
    if last_transition:
        print("  Last transition:")
        print(f"    From: {last_transition['previous_state']}")
        print(f"    To: {last_transition['next_state']}")
        print(f"    Duration: {last_transition['duration']:.2f}s")
        print(f"    At: {last_transition['last_updated']}")
        
        # Simple prediction: use last duration
        predicted_duration = float(last_transition['duration'])
        next_state = 'GREEN' if current_state == 'RED' else 'RED'
        
        print("\n[3] Prediction:")
        print(f"  Next state: {next_state}")
        print(f"  Expected duration: {predicted_duration:.2f}s")
    else:
        print("  No transitions found for this light_id")
    
    print("\n[4] Raw data inspection:")
    cursor.execute("""
        SELECT previous_state, next_state, duration, last_updated
        FROM state_durations 
        WHERE light_id = ?
        ORDER BY last_updated DESC
        LIMIT 10
    """, (light_id,))
    
    raw_data = cursor.fetchall()
    
    if raw_data:
        print("Most recent transitions:")
        for row in raw_data:
            try:
                duration = float(row['duration'])
                print(f"  {row['previous_state']}->{row['next_state']}: "
                      f"{duration:.2f}s at {row['last_updated']}")
            except (ValueError, TypeError) as e:
                print(f"  Invalid duration data: {e}")
                continue
    else:
        print("  No raw data found for this light_id")
    
    conn.close()

if __name__ == "__main__":
    debug_prediction_query()
