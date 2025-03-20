import sqlite3
import time
from collections import defaultdict
from datetime import datetime

from flask import Flask, jsonify

app = Flask(__name__)
DB_PATH = "/data/detectors.db"

def predict_next_change(light_id, current_state):
    """Predict next change using duration of same type of recent transition"""
    # If current state is not valid, return default values
    if current_state not in ('RED', 'GREEN'):
        print(f"[PREDICT] Light {light_id}: Invalid current state '{current_state}', using defaults")
        return ('UNKNOWN', 0, 0.0)
    
    print(f"\n[PREDICT] Starting prediction for Light {light_id}, current state: {current_state}")
    
    # Define default durations for each state transition
    DEFAULT_DURATIONS = {
        'RED': {'next': 'GREEN', 'duration': 30},
        'GREEN': {'next': 'RED', 'duration': 60}
    }
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Get last transition of the same type
        cursor.execute("""
            SELECT previous_state, next_state, duration, last_updated
            FROM state_durations
            WHERE light_id = ? AND previous_state = ?
            ORDER BY last_updated DESC
            LIMIT 1
        """, (light_id, current_state))
        
        last_transition = cursor.fetchone()
        
        if last_transition:
            # Use duration from same type transition
            predicted_duration = float(last_transition['duration'])
            next_state = last_transition['next_state']
            
            print(f"[PREDICT] Found transition data: {current_state}->{next_state}, duration={predicted_duration:.2f}s, updated={last_transition['last_updated']}")
            
            # Check if we have stale timestamps (from 2019 or earlier)
            current_year = datetime.now().year
            
            # Get the most recent timestamp when this state started
            cursor.execute('''
                SELECT timestamp 
                FROM traffic_light_states
                WHERE light_id = ? AND state = ?
                ORDER BY timestamp DESC
                LIMIT 1
            ''', (light_id, current_state))
            
            result = cursor.fetchone()
            
            if result and result['timestamp']:
                # Debug the timestamp value
                print(f"[PREDICT] Raw timestamp from DB: {result['timestamp']} (type: {type(result['timestamp']).__name__})")
                
                # Convert timestamp to seconds since epoch
                try:
                    # Handle both integer timestamps and ISO format strings
                    current_time = time.time()
                    print(f"[PREDICT] Current time: {current_time} ({datetime.fromtimestamp(current_time).isoformat()})")
                    
                    timestamp_year = None
                    if isinstance(result['timestamp'], int):
                        current_state_start = result['timestamp']
                        # Check if timestamp is from a reasonable time period
                        timestamp_year = datetime.fromtimestamp(current_state_start).year
                        print(f"[PREDICT] Timestamp is integer: {current_state_start} (year: {timestamp_year})")
                    else:
                        # Try parsing as ISO format
                        try:
                            dt = datetime.fromisoformat(result['timestamp'])
                            current_state_start = time.mktime(dt.timetuple())
                            timestamp_year = dt.year
                            print(f"[PREDICT] Parsed ISO timestamp: {current_state_start} (year: {timestamp_year})")
                        except ValueError:
                            # Try parsing as float/int string
                            current_state_start = float(result['timestamp'])
                            timestamp_year = datetime.fromtimestamp(current_state_start).year
                            print(f"[PREDICT] Parsed numeric timestamp: {current_state_start} (year: {timestamp_year})")
                    
                    # Check if timestamp is too old (more than 1 day old)
                    if timestamp_year < current_year - 1 or current_time - current_state_start > 86400:
                        print(f"[PREDICT] Timestamp is too old ({timestamp_year}), updating to current time")
                    
                        # Instead of using defaults, update the timestamp to current time
                        # This fixes the old timestamp issue by creating a new record with current time
                        try:
                            update_cursor = conn.cursor()
                            # Insert a new state record with current timestamp
                            update_cursor.execute("""
                                INSERT INTO traffic_light_states (light_id, state, timestamp)
                                VALUES (?, ?, ?)
                            """, (light_id, current_state, int(current_time)))
                            conn.commit()
                            print(f"[PREDICT] Updated timestamp for light {light_id} to current time")
                        
                            # Now use a small portion of the predicted duration as time remaining
                            # This assumes the light just changed to this state
                            time_remaining = predicted_duration * 0.9  # Assume we're at the start of the cycle
                            confidence = 0.7  # Medium confidence for updated timestamps
                        except Exception as update_error:
                            print(f"[PREDICT] Error updating timestamp: {update_error}")
                            time_remaining = predicted_duration * 0.5  # Fallback to halfway through cycle
                            confidence = 0.5  # Lower confidence for default predictions
                    else:
                        # Normal calculation for recent timestamps
                        current_state_duration = current_time - current_state_start
                        print(f"[PREDICT] Current state duration: {current_state_duration:.2f}s")
                        print(f"[PREDICT] Predicted total duration: {predicted_duration:.2f}s")
                        
                        time_remaining = max(0, predicted_duration - current_state_duration)
                        confidence = 1.0  # Full confidence for recent timestamps
                    
                    print(f"[PREDICT] Light {light_id} ({current_state}): Next={next_state}, "
                          f"Remaining={time_remaining:.2f}s, Confidence={confidence:.2f}")
                    
                    # Query for all recent state changes for this light for debugging
                    cursor.execute('''
                        SELECT state, timestamp
                        FROM traffic_light_states
                        WHERE light_id = ?
                        ORDER BY timestamp DESC
                        LIMIT 5
                    ''', (light_id,))
                    
                    recent_states = cursor.fetchall()
                    print(f"[PREDICT] Recent state changes for light {light_id}:")
                    for i, state in enumerate(recent_states):
                        print(f"  {i+1}. {state['state']} at {state['timestamp']}")
                
                    return (next_state, time_remaining, confidence)
                except (ValueError, TypeError) as e:
                    print(f"[PREDICT] Error parsing timestamp for light {light_id}: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"[PREDICT] No timestamp found for current state of light {light_id}")
                
                # Check if there are any state records at all
                cursor.execute('''
                    SELECT COUNT(*) as count
                    FROM traffic_light_states
                    WHERE light_id = ?
                ''', (light_id,))
                
                count = cursor.fetchone()['count']
                print(f"[PREDICT] Total state records for light {light_id}: {count}")
        else:
            print(f"[PREDICT] No transition data found for light {light_id} with state {current_state}")
            
            # Check if there are any transitions at all
            cursor.execute('''
                SELECT COUNT(*) as count
                FROM state_durations
                WHERE light_id = ?
            ''', (light_id,))
            
            count = cursor.fetchone()['count']
            print(f"[PREDICT] Total transition records for light {light_id}: {count}")
            
            if count > 0:
                # Show available transitions
                cursor.execute('''
                    SELECT previous_state, next_state, duration, last_updated
                    FROM state_durations
                    WHERE light_id = ?
                    ORDER BY last_updated DESC
                ''', (light_id,))
                
                transitions = cursor.fetchall()
                print(f"[PREDICT] Available transitions for light {light_id}:")
                for t in transitions:
                    print(f"  {t['previous_state']}->{t['next_state']}: {t['duration']:.2f}s (updated: {t['last_updated']})")
        
        # Fallback to defaults if no transitions found or timestamp issues
        print(f"[PREDICT] Light {light_id}: Using default prediction values")
        
        # Use the predefined defaults
        next_state = DEFAULT_DURATIONS[current_state]['next']
        default_duration = DEFAULT_DURATIONS[current_state]['duration']
        
        # Create a new timestamp record to establish history
        try:
            current_time = time.time()
            cursor.execute("""
                INSERT INTO traffic_light_states (light_id, state, timestamp)
                VALUES (?, ?, ?)
            """, (light_id, current_state, int(current_time)))
            conn.commit()
            print(f"[PREDICT] Created new timestamp record for light {light_id}")
        except Exception as e:
            print(f"[PREDICT] Error creating timestamp record: {e}")
            
        return (next_state, default_duration, 0.5)
    
    except Exception as e:
        print(f"[PREDICT] Error predicting next change for light {light_id}: {e}")
        import traceback
        traceback.print_exc()
        # Return safe defaults
        next_state = 'GREEN' if current_state == 'RED' else 'RED'
        return (next_state, 45, 0.3)
    
    finally:
        conn.close()

def get_intersection_status(intersection_id):
    """Get current status of an intersection from the database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Ensure the table exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS traffic_light_states (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            light_id INTEGER NOT NULL,
            state TEXT CHECK(state IN ('RED', 'GREEN')) NOT NULL,
            timestamp DATETIME NOT NULL,
            FOREIGN KEY (light_id) REFERENCES traffic_lights(light_id)
        )
    """)
    
    # Get latest states for all lights in the intersection
    cursor.execute("""
        SELECT tl.light_id, tl.name, tl.location, tls.state, tls.timestamp 
        FROM traffic_lights tl
        JOIN (
            SELECT light_id, MAX(rowid) as max_rowid
            FROM traffic_light_states
            GROUP BY light_id
        ) latest ON tl.light_id = latest.light_id
        JOIN traffic_light_states tls ON tls.rowid = latest.max_rowid
        WHERE tl.intersection_id = ?
    """, (intersection_id,))
    
    lights = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    if not lights:
        return None
    
    # Format response
    traffic_lights = []
    for light in lights:
        # Make a single prediction call per light
        next_state, time_remaining, confidence = predict_next_change(light['light_id'], light['state'])
        
        traffic_lights.append({
            "light_id": light['light_id'],
            "current_status": light['state'],
            "time_to_next_change_seconds": time_remaining,
            "predicted_next_status": next_state,
            "prediction_confidence": confidence,
            "location": {
                "latitude": float(light['location'].split(',')[0].strip()),
                "longitude": float(light['location'].split(',')[1].strip())
            },
            "name": light['name']
        })
    
    return {
        "intersection_id": intersection_id,
        "timestamp": datetime.now().isoformat(),
        "traffic_lights": traffic_lights
    }

@app.route('/status/<intersection_id>')
def get_status(intersection_id):
    status = get_intersection_status(intersection_id)
    if not status:
        return jsonify({"error": "Intersection not found"}), 404
    return jsonify(status)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=6000)
