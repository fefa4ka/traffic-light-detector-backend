# Traffic Light Monitoring System

## Table of Contents
1. [System Setup](#system-setup)
2. [Managing Traffic Lights](#managing-traffic-lights)
3. [Monitoring & API](#monitoring--api)
4. [Testing & Development](#testing--development)
5. [Database Maintenance](#database-maintenance)

## System Setup

### First Time Deployment
```bash
# Build and start container with test data
./run_dev_setup.sh

# Access services:
# - MQTT Broker: localhost:1883
# - API Server: http://localhost:6000
# - MQTT Publisher: Active
```

### Production Deployment
```bash
# First deployment
chmod +x run_prod.sh
./run_prod.sh

# Subsequent updates
./run_prod.sh  # Re-runs with clean deployment
```

The script will:
1. Build fresh Docker image
2. Stop/remove any existing container
3. Deploy new container with proper ports and data volume
4. Preserve existing data between deployments through the ./data directory

## Nginx Reverse Proxy Setup
For production deployments, we recommend using Nginx as a reverse proxy:

```bash
# Install Nginx
sudo apt install nginx
```

Create a new config file `/etc/nginx/sites-available/traffic-lights`:
```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://localhost:6000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the configuration:
```bash
sudo ln -s /etc/nginx/sites-available/traffic-lights /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## Managing Traffic Lights

### Create New Traffic Light
```bash
docker exec -it tld_backend python3 /app/group_traffic_lights.py
```
Follow interactive prompts to:
1. Name the light
2. Set location coordinates (format: "lat, lng")
3. Assign detector ID
4. Configure RED/GREEN channels (0-31)

### Group Lights into Intersections
```bash
docker exec -it tld_backend python3 /app/manage_intersections.py
```
Steps:
1. View existing lights
2. Enter intersection name/location
3. Select light IDs to include

## Monitoring & API

### View All Intersections
```bash
docker exec tld_backend python3 /app/list_intersections.py
```

### Get Real-Time Status
```bash
# Get intersection status
curl http://localhost:6000/status/Downtown_Crossing_202503071200

# Response includes:
# - Current light states
# - Location coordinates
# - Last update timestamp
```

### View Raw Telemetry
```bash
docker exec tld_backend python3 /app/display_traffic_lights.py
```

## Testing & Development

### Load Test Data
```bash
# Load 4-light intersection with detector 1
docker exec tld_backend python3 /app/load_fixtures.py

# Generate test traffic patterns
docker exec tld_backend python3 /app/test_mqtt_publisher.py
```

### View Debug Outputs
```bash
# See raw MQTT messages
docker logs tld_backend -f

# View API server logs
docker exec tld_backend tail -f /var/log/mosquitto/mosquitto.log
```

## Database Maintenance

### Backup Database
```bash
docker exec tld_backend sqlite3 /data/detectors.db .dump > backup.sql
```

### Restore Database
```bash
cat backup.sql | docker exec -i tld_backend sqlite3 /data/detectors.db
```

### Reset System
```bash
# Wipe all data and restart
rm -rf data/*
./run_dev_setup.sh
```
