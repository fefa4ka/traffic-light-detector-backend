# Creating a New Traffic Light Detector Account

To add a new traffic light detector, follow these steps:

1. **Register the detector using Docker:**
   ```bash
   docker exec tld_backend python3 /app/register_detector.py detector_name
   ```

   - Replace `detector_name` with the unique identifier for the new detector.
   - The script will generate a password for the MQTT connection.

2. **Retrieve and store the credentials:**
   - The output of the command will display the generated password.
   - Store this password securely as it will be required for MQTT authentication.

This process ensures that new detectors are securely registered with MQTT and stored in the database.

# Deploying and Updating the Docker Container

## Deploy
To build and start the Docker container:
```bash
docker build -t traffic-light-backend .
docker run -d --name tld_backend -p 1883:1883 -p 9001:9001 traffic-light-backend
```

## Update
To update the container with new changes:
```bash
docker stop tld_backend
docker rm tld_backend
docker build -t traffic-light-backend .
docker run -d --name tld_backend -p 1883:1883 -p 9001:9001 traffic-light-backend
```
