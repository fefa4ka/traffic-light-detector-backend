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

# Listing Registered Traffic Light Detectors

To list all registered traffic light detectors, run:

```bash
docker exec tld_backend python3 /app/list_detectors.py
```

This will output the detector names and their associated passwords.

# Verifying Detector Registration

## Check if the user was created in Mosquitto
To verify that the MQTT user was created, inspect the password file inside the container:

```bash
docker exec tld_backend cat /mosquitto/config/passwords
```

If the detector appears in the file, it was successfully registered.

## Test Connection to the MQTT Broker
To check that the new detector can connect to the broker, use the following command:

```bash
mosquitto_sub -h localhost -p 1883 -u detector_name -P detector_password -t "#"
```

Replace `detector_name` and `detector_password` with the credentials generated during registration. If the connection succeeds, the detector is properly configured.

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
