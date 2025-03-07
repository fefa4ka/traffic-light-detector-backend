#!/bin/sh

# Start MQTT listener in background
python3 /app/mqtt_listener.py &

# Start API server in foreground
python3 /app/api_server.py

# Keep container running
wait
