# Use the official Eclipse Mosquitto image
FROM eclipse-mosquitto:latest

# Install required dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    sqlite \
    protobuf 

# Set up a virtual environment
RUN python3 -m venv /app/venv

# Activate the virtual environment and install dependencies
RUN /app/venv/bin/pip install --no-cache-dir \
    paho-mqtt \
    protobuf \
    flask

# Ensure all scripts use the virtual environment's Python
ENV PATH="/app/venv/bin:$PATH"

# Ensure external storage for passwords and database
VOLUME ["/data"]
RUN mkdir -p /data && touch /data/passwords /data/detectors.db && chmod 600 /data/passwords

# Copy telemetry.proto before compiling
COPY telemetry.proto /app/telemetry.proto

# Compile protobuf files with correct proto path
RUN protoc --proto_path=/app --python_out=/app /app/telemetry.proto

# Copy Mosquitto authentication configuration
COPY mosquitto.conf /mosquitto/config/mosquitto.conf

# Copy all Python scripts dynamically
COPY *.py /app/

# Set the working directory
WORKDIR /app

# Expose default Mosquitto ports and API port
EXPOSE 1883 6000

# Copy startup script
COPY start_services.sh /app/start_services.sh

# Ensure required directories and files exist before starting services
CMD mkdir -p /data && touch /data/passwords /data/detectors.db && \
    chown mosquitto:mosquitto /data/passwords && chmod 640 /data/passwords && \
    /usr/sbin/mosquitto -c /mosquitto/config/mosquitto.conf & \
    sh /app/start_services.sh
