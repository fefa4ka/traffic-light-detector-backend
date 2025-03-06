# Use the official Eclipse Mosquitto image
FROM eclipse-mosquitto:latest

# Install required dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    sqlite \
    protobuf

# Ensure external storage for passwords and database
VOLUME ["/data"]
RUN mkdir -p /data && touch /data/passwords /data/detectors.db && chmod 600 /data/passwords

# Compile protobuf files
RUN protoc --python_out=/app /app/telemetry.proto

# Copy Mosquitto authentication configuration
COPY mosquitto.conf /mosquitto/config/mosquitto.conf
COPY register_detector.py /app/register_detector.py
COPY list_detectors.py /app/list_detectors.py

# Set the working directory
WORKDIR /app

# Expose default Mosquitto ports
EXPOSE 1883 9001

# Ensure required directories and files exist before starting Mosquitto
CMD mkdir -p /data && touch /data/passwords /data/detectors.db && chmod 600 /data/passwords && \
    /usr/sbin/mosquitto -c /mosquitto/config/mosquitto.conf
