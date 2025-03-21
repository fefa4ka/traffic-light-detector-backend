#!/usr/bin/env python3
import sqlite3
import time
from datetime import datetime, timedelta

DB_PATH = "/data/detectors.db"

def fix_unreasonable_durations():
    """Fix unreasonable durations in the database by adjusting timestamps"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("Starting duration fix process...")
    
    try:
        # 1. Get all traffic lights
        cursor.execute("SELECT light_id, name FROM traffic_lights")
        lights = cursor.fetchall()
        
        for light_id, name in lights:
            print(f"\nAnalyzing light {light_id} ({name})...")
            
            # 2. Get all state transitions for this light
            cursor.execute("""
                SELECT id, state, timestamp 
                FROM traffic_light_states 
                WHERE light_id = ? 
                ORDER BY timestamp ASC
            """, (light_id,))
            
            states = cursor.fetchall()
            
            if len(states) < 2:
                print(f"  Not enough state records for light {light_id}, skipping")
                continue
                
            print(f"  Found {len(states)} state records")
            
            # 3. Analyze and fix timestamps
            prev_state = None
            prev_timestamp = None
            prev_id = None
            
            fixed_count = 0
            
            for i, (state_id, state, timestamp) in enumerate(states):
                # Skip first record
                if prev_state is None:
                    prev_state = state
                    prev_timestamp = timestamp
                    prev_id = state_id
                    continue
                
                # Calculate duration
                try:
                    # Ensure timestamps are numeric
                    if isinstance(prev_timestamp, str) and not prev_timestamp.isdigit():
                        prev_timestamp = int(datetime.fromisoformat(prev_timestamp).timestamp())
                    else:
                        prev_timestamp = int(float(prev_timestamp))
                        
                    if isinstance(timestamp, str) and not timestamp.isdigit():
                        timestamp = int(datetime.fromisoformat(timestamp).timestamp())
                    else:
                        timestamp = int(float(timestamp))
                    
                    duration = timestamp - prev_timestamp
                    
                    # Check if duration is unreasonable
                    if duration < 5 or duration > 300:
                        print(f"  Unreasonable duration ({duration}s) between states {prev_id} and {state_id}")
                        
                        # Determine reasonable duration based on state
                        reasonable_duration = 30 if prev_state == 'RED' else 15
                        
                        # Calculate new timestamp
                        new_timestamp = prev_timestamp + reasonable_duration
                        
                        # Update the timestamp
                        cursor.execute("""
                            UPDATE traffic_light_states
                            SET timestamp = ?
                            WHERE id = ?
                        """, (new_timestamp, state_id))
                        
                        print(f"  Fixed: Updated timestamp for state {state_id} from {timestamp} to {new_timestamp}")
                        fixed_count += 1
                        
                        # Update for next iteration
                        timestamp = new_timestamp
                
                except Exception as e:
                    print(f"  Error processing duration: {e}")
                
                # Update for next iteration
                prev_state = state
                prev_timestamp = timestamp
                prev_id = state_id
            
            print(f"  Fixed {fixed_count} unreasonable durations for light {light_id}")
            
            # 4. Update state_durations table with correct values
            if fixed_count > 0:
                print("  Recalculating state durations...")
                
                # Get all transitions (RED->GREEN and GREEN->RED)
                cursor.execute("""
                    SELECT s1.state as prev_state, s2.state as next_state, 
                           s1.timestamp as start_time, s2.timestamp as end_time
                    FROM traffic_light_states s1
                    JOIN traffic_light_states s2 ON s1.light_id = s2.light_id
                    WHERE s1.light_id = ? 
                      AND s1.state != s2.state
                      AND s1.timestamp < s2.timestamp
                      AND s1.state IN ('RED', 'GREEN')
                      AND s2.state IN ('RED', 'GREEN')
                      AND NOT EXISTS (
                          SELECT 1 FROM traffic_light_states s3
                          WHERE s3.light_id = s1.light_id
                            AND s3.timestamp > s1.timestamp
                            AND s3.timestamp < s2.timestamp
                      )
                    ORDER BY s1.timestamp ASC
                """, (light_id,))
                
                transitions = cursor.fetchall()
                
                if not transitions:
                    print("  No valid transitions found after fixing")
                    continue
                
                # Calculate average durations for each transition type
                red_to_green_durations = []
                green_to_red_durations = []
                
                for prev_state, next_state, start_time, end_time in transitions:
                    duration = end_time - start_time
                    
                    if 5 <= duration <= 300:  # Only use reasonable durations
                        if prev_state == 'RED' and next_state == 'GREEN':
                            red_to_green_durations.append(duration)
                        elif prev_state == 'GREEN' and next_state == 'RED':
                            green_to_red_durations.append(duration)
                
                # Calculate averages
                if red_to_green_durations:
                    avg_red_to_green = sum(red_to_green_durations) / len(red_to_green_durations)
                    print(f"  Average RED->GREEN duration: {avg_red_to_green:.2f}s")
                    
                    # Update state_durations table
                    cursor.execute("""
                        INSERT OR REPLACE INTO state_durations
                        (light_id, previous_state, next_state, duration, last_updated)
                        VALUES (?, ?, ?, ?, ?)
                    """, (light_id, 'RED', 'GREEN', avg_red_to_green, datetime.now().isoformat()))
                
                if green_to_red_durations:
                    avg_green_to_red = sum(green_to_red_durations) / len(green_to_red_durations)
                    print(f"  Average GREEN->RED duration: {avg_green_to_red:.2f}s")
                    
                    # Update state_durations table
                    cursor.execute("""
                        INSERT OR REPLACE INTO state_durations
                        (light_id, previous_state, next_state, duration, last_updated)
                        VALUES (?, ?, ?, ?, ?)
                    """, (light_id, 'GREEN', 'RED', avg_green_to_red, datetime.now().isoformat()))
        
        # Commit all changes
        conn.commit()
        print("\nAll duration fixes completed and committed to database")
        
    except Exception as e:
        print(f"Error fixing durations: {e}")
        conn.rollback()
        import traceback
        traceback.print_exc()
    
    finally:
        conn.close()

def analyze_traffic_patterns():
    """Analyze traffic light patterns to determine typical durations"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("\nAnalyzing traffic patterns...")
    
    try:
        # Get all traffic lights
        cursor.execute("SELECT light_id, name FROM traffic_lights")
        lights = cursor.fetchall()
        
        for light_id, name in lights:
            print(f"\nLight {light_id} ({name}) patterns:")
            
            # Get state transitions with durations
            cursor.execute("""
                SELECT s1.state as prev_state, s2.state as next_state, 
                       s1.timestamp as start_time, s2.timestamp as end_time,
                       (s2.timestamp - s1.timestamp) as duration
                FROM traffic_light_states s1
                JOIN traffic_light_states s2 ON s1.light_id = s2.light_id
                WHERE s1.light_id = ? 
                  AND s1.state != s2.state
                  AND s1.timestamp < s2.timestamp
                  AND s1.state IN ('RED', 'GREEN')
                  AND s2.state IN ('RED', 'GREEN')
                  AND NOT EXISTS (
                      SELECT 1 FROM traffic_light_states s3
                      WHERE s3.light_id = s1.light_id
                        AND s3.timestamp > s1.timestamp
                        AND s3.timestamp < s2.timestamp
                  )
                ORDER BY s1.timestamp ASC
            """, (light_id,))
            
            transitions = cursor.fetchall()
            
            if not transitions:
                print("  No transitions found")
                continue
            
            print(f"  Found {len(transitions)} transitions")
            
            # Group by transition type
            red_to_green = [t for t in transitions if t[0] == 'RED' and t[1] == 'GREEN']
            green_to_red = [t for t in transitions if t[0] == 'GREEN' and t[1] == 'RED']
            
            # Analyze RED->GREEN transitions
            if red_to_green:
                durations = [t[4] for t in red_to_green if 5 <= t[4] <= 300]
                if durations:
                    avg_duration = sum(durations) / len(durations)
                    min_duration = min(durations)
                    max_duration = max(durations)
                    print(f"  RED->GREEN: {len(durations)} valid transitions")
                    print(f"    Average: {avg_duration:.2f}s")
                    print(f"    Range: {min_duration:.2f}s - {max_duration:.2f}s")
                else:
                    print("  RED->GREEN: No valid transitions")
            
            # Analyze GREEN->RED transitions
            if green_to_red:
                durations = [t[4] for t in green_to_red if 5 <= t[4] <= 300]
                if durations:
                    avg_duration = sum(durations) / len(durations)
                    min_duration = min(durations)
                    max_duration = max(durations)
                    print(f"  GREEN->RED: {len(durations)} valid transitions")
                    print(f"    Average: {avg_duration:.2f}s")
                    print(f"    Range: {min_duration:.2f}s - {max_duration:.2f}s")
                else:
                    print("  GREEN->RED: No valid transitions")
            
            # Check current state durations table
            cursor.execute("""
                SELECT previous_state, next_state, duration, last_updated
                FROM state_durations
                WHERE light_id = ?
            """, (light_id,))
            
            durations = cursor.fetchall()
            
            print("  Current state_durations table:")
            for prev_state, next_state, duration, last_updated in durations:
                print(f"    {prev_state}->{next_state}: {duration:.2f}s (updated: {last_updated})")
    
    except Exception as e:
        print(f"Error analyzing patterns: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        conn.close()

def main():
    print("Traffic Light Duration Debug Tool")
    print("================================")
    
    while True:
        print("\nOptions:")
        print("1. Fix unreasonable durations")
        print("2. Analyze traffic patterns")
        print("3. Exit")
        
        choice = input("\nEnter your choice (1-3): ")
        
        if choice == '1':
            fix_unreasonable_durations()
        elif choice == '2':
            analyze_traffic_patterns()
        elif choice == '3':
            print("Exiting...")
            break
        else:
            print("Invalid choice, please try again")

if __name__ == "__main__":
    main()
