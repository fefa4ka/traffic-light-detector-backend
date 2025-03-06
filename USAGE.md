# Creating a New Traffic Light Detector Account in Docker

To register a new traffic light detector without entering the running container, follow these steps:

1. **Run the registration script inside the container:**
   ```bash
   docker exec mosquitto python3 register_detector.py detector_name
   ```

   Replace `detector_name` with the desired name for the new detector.

2. **The script will output the generated password**, which will be required for MQTT authentication.

This allows you to create detector accounts efficiently without needing to access the container shell manually.
