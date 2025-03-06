# Creating a New Traffic Light Detector Account in Docker

To register a new traffic light detector inside a Docker container running Mosquitto, follow these steps:

1. **Enter the running container:**
   ```bash
   docker exec -it mosquitto sh
   ```

2. **Run the registration script inside the container:**
   ```bash
   python3 register_detector.py detector_name
   ```

   Replace `detector_name` with the identifier for the new detector.

3. **Note the generated password,** as it will be required for MQTT authentication.
