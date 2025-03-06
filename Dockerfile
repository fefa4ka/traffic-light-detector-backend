# Use the official Eclipse Mosquitto image
FROM eclipse-mosquitto:latest

# Install required dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    sqlite3 && \
    rm -rf /var/lib/apt/lists/*

# Expose default Mosquitto ports
EXPOSE 1883 9001

# Command to start Mosquitto
CMD ["/usr/sbin/mosquitto", "-c", "/mosquitto/config/mosquitto.conf"]
