import sqlite3
from datetime import datetime

DB_PATH = "/data/detectors.db"

def debug_prediction_query():
    """Interactive debugger for the prediction SQL query"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("Prediction Query Debugger\n" + "="*30)
    
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
    
    if table_exists:
        print("\n[2] Checking for records in state_durations...")
        cursor.execute("SELECT COUNT(*) FROM state_durations WHERE light_id = ?", (light_id,))
        count = cursor.fetchone()[0]
        print(f"  Found {count} total records for light_id={light_id}")
        
        cursor.execute("""
            SELECT COUNT(*) FROM state_durations 
            WHERE light_id = ? AND previous_state = ?
        """, (light_id, current_state))
        count_filtered = cursor.fetchone()[0]
        print(f"  Found {count_filtered} records with previous_state={current_state}")
    
    print("\n[3] Executing full prediction query...")
    query = """
        SELECT previous_state, next_state, 
               SUM(duration * weight)/SUM(weight) as weighted_avg,
               COUNT(*) as samples
        FROM (
            SELECT *, 
                   EXP(-0.001 * (strftime('%s','now') - last_updated)) as weight
            FROM state_durations
            WHERE light_id = ? AND previous_state = ?
            ORDER BY last_updated DESC
            LIMIT 100
        )
        GROUP BY previous_state, next_state
        HAVING samples >= 3
    """
    print("SQL Query:\n" + query)
    print(f"Parameters: light_id={light_id}, current_state={current_state}")
    
    cursor.execute(query, (light_id, current_state))
    results = cursor.fetchall()
    
    print("\n[4] Query Results:")
    if not results:
        print("  No results returned")
    else:
        for i, row in enumerate(results, 1):
            print(f"  Result {i}:")
            print(f"    Previous: {row['previous_state']}")
            print(f"    Next: {row['next_state']}")
            print(f"    Weighted Avg: {row['weighted_avg']:.2f}")
            print(f"    Samples: {row['samples']}")
    
    print("\n[5] Raw data inspection:")
    try:
        cursor.execute("""
            SELECT previous_state, next_state, duration, last_updated
            FROM state_durations 
            WHERE light_id = ?
            ORDER BY last_updated DESC
        """, (light_id,))
    except sqlite3.Error as e:
        print(f"  Error querying raw data: {e}")
        return
    raw_data = cursor.fetchall()
    
    if raw_data:
        print("Most recent 10 state_durations records:")
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
