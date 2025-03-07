#!/bin/zsh

# Stop and remove any existing container
docker stop tld_backend 2>/dev/null
docker rm tld_backend 2>/dev/null

# Rebuild and start new container
docker build -t traffic-light-backend .
docker run -d --name tld_backend -p 1883:1883 -p 9001:9001 -v $(pwd)/data:/data traffic-light-backend

# Wait for database to be ready
sleep 5

# Clear existing database and load fixtures
docker exec tld_backend /bin/sh -c "rm -f /data/detectors.db && python3 /app/load_fixtures.py"

# Run services in parallel with output visible
echo "Waiting for detector registration..."
docker exec tld_backend python3 /app/register_detector.py detector

echo -e "\nStarting services..."
echo "======================="
echo "Starting MQTT listener..."
docker exec -d tld_backend python3 /app/mqtt_listener.py
echo "Starting MQTT publisher..."
docker exec -d tld_backend python3 /app/test_mqtt_publisher.py
echo "Starting API server..."
docker exec -it tld_backend python3 /app/api_server.py

echo -e "\nServices running:"
echo "  - MQTT Broker: localhost:1883"
echo "  - API Server:  http://localhost:5000"
echo "  - MQTT Publisher: Active"
echo -e "\nTry: curl http://localhost:5000/status/Downtown_Crossing_*"

# Keep script running
while true; do sleep 1; done

# Keep script running until background processes finish
wait
