import sqlite3
from collections import defaultdict
from datetime import datetime

from flask import Flask, jsonify
from mqtt_listener import predict_next_change

app = Flask(__name__)
DB_PATH = "/data/detectors.db"

def get_intersection_status(intersection_id):
    """Get current status of an intersection from the database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get latest states for all lights in the intersection
    cursor.execute("""
        SELECT tl.light_id, tl.name, tl.location, tls.state, tls.timestamp 
        FROM traffic_lights tl
        JOIN (
            SELECT light_id, MAX(timestamp) as max_ts
            FROM traffic_light_states
            GROUP BY light_id
        ) latest ON tl.light_id = latest.light_id
        JOIN traffic_light_states tls ON tl.light_id = tls.light_id AND tls.timestamp = latest.max_ts
        WHERE tl.intersection_id = ?
    """, (intersection_id,))
    
    lights = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    if not lights:
        return None
    
    # Format response
    return {
        "intersection_id": intersection_id,
        "timestamp": datetime.now().isoformat(),
        "traffic_lights": [{
            "light_id": light['light_id'],
            "current_status": light['state'],
            "time_to_next_change_seconds": predict_next_change(light['light_id'], light['state'])[1],
            "predicted_next_status": predict_next_change(light['light_id'], light['state'])[0],
            "prediction_confidence": predict_next_change(light['light_id'], light['state'])[2],
            "location": {
                "latitude": float(light['location'].split(',')[0].strip()),
                "longitude": float(light['location'].split(',')[1].strip())
            },
            "name": light['name']
        } for light in lights]
    }

@app.route('/status/<intersection_id>')
def get_status(intersection_id):
    status = get_intersection_status(intersection_id)
    if not status:
        return jsonify({"error": "Intersection not found"}), 404
    return jsonify(status)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=6000)
