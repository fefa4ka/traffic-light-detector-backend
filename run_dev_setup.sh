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
echo -e "\nStarting MQTT services..."
echo "==========================="
docker exec -it tld_backend python3 /app/test_mqtt_publisher.py &
docker exec -it tld_backend python3 /app/mqtt_listener.py

# Keep script running until background processes finish
wait
