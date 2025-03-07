#!/bin/zsh

# Production deployment script for traffic light backend
set -e

# Build image
docker build -t traffic-light-backend .

# Stop and remove existing container if running
docker stop tld_backend 2>/dev/null || true
docker rm tld_backend 2>/dev/null || true

# Run new container with production settings
docker run -d --name tld_backend \
  -p 1883:1883 \
  -p 9001:9001 \
  -p 6000:6000 \
  -v $(pwd)/data:/data \
  traffic-light-backend

echo -e "\n\033[1;32mProduction deployment successful!\033[0m"
echo -e "Access services:"
echo "  - MQTT Broker:    localhost:1883"
echo "  - WebSocket:      localhost:9001"
echo "  - API Server:     http://localhost:6000"
echo -e "\nMonitor logs with: docker logs tld_backend -f"
