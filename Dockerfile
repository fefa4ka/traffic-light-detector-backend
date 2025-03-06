# Use the official Eclipse Mosquitto image
FROM eclipse-mosquitto:latest

# Expose default Mosquitto ports
EXPOSE 1883 9001

# Command to start Mosquitto
CMD ["/usr/sbin/mosquitto", "-c", "/mosquitto/config/mosquitto.conf"]
