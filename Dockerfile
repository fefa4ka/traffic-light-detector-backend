# Use the official Eclipse Mosquitto image
FROM eclipse-mosquitto:latest

# Install required dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    sqlite

# Ensure the password file exists with correct permissions
RUN mkdir -p /mosquitto/config && touch /mosquitto/config/passwords && chmod 600 /mosquitto/config/passwords

# Copy Mosquitto authentication configuration
COPY mosquitto.conf /mosquitto/config/mosquitto.conf
COPY register_detector.py /app/register_detector.py
COPY list_detectors.py /app/list_detectors.py

# Set the working directory
WORKDIR /app

# Expose default Mosquitto ports
EXPOSE 1883 9001

# Command to start Mosquitto
CMD ["/usr/sbin/mosquitto", "-c", "/mosquitto/config/mosquitto.conf"]
