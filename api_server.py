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
                # Convert timestamp to seconds since epoch
                try:
                    # Handle both integer timestamps and ISO format strings
                    if isinstance(result['timestamp'], int):
                        current_state_start = result['timestamp']
                    else:
                        current_state_start = time.mktime(datetime.fromisoformat(result['timestamp']).timetuple())
                    
                    current_state_duration = time.time() - current_state_start
                    time_remaining = max(0, predicted_duration - current_state_duration)
                    confidence = 1.0  # Always confident in last transition
                    
                    print(f"\n[PREDICT] Light {light_id} ({current_state}): Next={next_state}, "
                          f"Remaining={time_remaining:.2f}s, Confidence={confidence:.2f}")
                
                    return (next_state, time_remaining, confidence)
                except (ValueError, TypeError) as e:
                    print(f"[PREDICT] Error parsing timestamp for light {light_id}: {e}")
            else:
                print(f"[PREDICT] No timestamp found for current state of light {light_id}")
        
        # Fallback to defaults if no transitions found or timestamp issues
        print(f"[PREDICT] Light {light_id}: Using default prediction values")
            
        if current_state == 'RED':
            next_state = 'GREEN'
            default_duration = 30  # Default RED->GREEN duration
        else:
            next_state = 'RED'
            default_duration = 60  # Default GREEN->RED duration
            
        return (next_state, default_duration, 0.5)
    
    except Exception as e:
        print(f"[PREDICT] Error predicting next change for light {light_id}: {e}")
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
