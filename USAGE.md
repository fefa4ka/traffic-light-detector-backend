# Creating a New Traffic Light Detector Account in Docker

To register a new traffic light detector without entering the running container, follow these steps:

1. **Run the registration script inside the container:**
   ```bash
   docker exec mosquitto python3 register_detector.py detector_name
   ```

   Replace `detector_name` with the desired name for the new detector.

2. **The script will output the generated password**, which will be required for MQTT authentication.

This allows you to create detector accounts efficiently without needing to access the container shell manually.

# Deploying and Updating the Docker Container

## Deploy
To build and start the Docker container:
```bash
docker build -t traffic-light-backend .
docker run -d --name mosquitto -p 1883:1883 -p 9001:9001 traffic-light-backend
```

## Update
To update the container with new changes:
```bash
docker stop mosquitto
docker rm mosquitto
docker build -t traffic-light-backend .
docker run -d --name mosquitto -p 1883:1883 -p 9001:9001 traffic-light-backend
```
