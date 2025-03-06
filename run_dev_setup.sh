#!/bin/zsh

# Stop and remove any existing containers
docker-compose down

# Rebuild and start new containers
docker-compose up -d --build

# Wait for database to be ready
sleep 5

# Clear existing database
rm -f /data/detectors.db

# Load test fixtures
python3 load_fixtures.py

# Run services in parallel
python3 mqtt_listener.py &
python3 test_mqtt_publisher.py &

# Keep script running until background processes finish
wait
