# Traffic Light Detector Backend
Backend for DEMO project. Traffic light detector attached to traffic light. There are channels that detect signals traffic light (RED, GREEN lights). The backend listens mqtt and stores the data in a database.


Telemetry from the traffic light detector is stored in a database. The database is used to calculate the prediction of the next traffic light change.
```protobuf
syntax = "proto3";

message mqtt_msg_t {
    int32 channels = 1;
    int32 timestamp = 2;
    int32 id = 3;
    int32 counter = 4;
}
```
`int32 channels` is a bit mask of the channels that are active.
Each channel represents a signal from some light, for example:
* Channel 1 - Red light of the traffic light A
* Channel 2 - Green light of the traffic light A
* Channel 4 - Red light of the traffic light B
* Channel 8 - Green light of the traffic light B

# Architecture and Implementation

## System Overview
The Traffic Light Detector Backend is designed to process MQTT telemetry data from traffic light detectors. The system consists of several components:

- **Mosquitto MQTT Broker:** Listens for telemetry messages from traffic lights.
- **Database:** Stores telemetry and processed data.
- **Telemetry Listener:** Subscribes to MQTT topics, processes messages, and stores them.
- **Aggregation Script:** Groups signals into readable traffic light states.
- **Backend API:** Provides access to the latest traffic light status.
- **Prediction Module:** Computes expected next signal change times.

## MQTT Message Structure
Telemetry messages are published in MQTT in the following protobuf format:
```protobuf
syntax = "proto3";

message mqtt_msg_t {
    int32 channels = 1;
    int32 timestamp = 2;
    int32 id = 3;
    int32 counter = 4;
}
```
The `channels` field is a bit mask indicating active signals.

## API Overview

The backend provides a REST API to retrieve real-time traffic light status.

### Endpoint: `GET /status/{intersection_id}`
Retrieves the current status of an intersection.

- **Path Parameter:** `intersection_id` (string) - Unique identifier of the monitored intersection.
- **Response:** JSON object containing the latest traffic signal data for that intersection.

Example Response:

```json
{
  "intersection_id": "intersection_001",
  "timestamp": "2023-10-01T12:00:00Z",
  "traffic_lights": [
    {
      "light_id": "tl_001_a",
      "current_status": "GREEN",
      "time_to_next_change_seconds": 45,
      "predicted_next_status": "RED",
              "location": {
    "latitude": 55.755826,
    "longitude": 37.617300
  },

    },
    {
      "light_id": "tl_001_b",
      "current_status": "RED",
      "time_to_next_change_seconds": 30,
      "predicted_next_status": "GREEN",
              "location": {
    "latitude": 55.755826,
    "longitude": 37.617300
  },

    },
    {
      "light_id": "tl_001_c",
      "current_status": "GREEN",
      "time_to_next_change_seconds": 10,
      "predicted_next_status": "RED",
              "location": {
    "latitude": 55.755826,
    "longitude": 37.617300
  },

    },
    {
      "light_id": "tl_001_d",
      "current_status": "RED",
      "time_to_next_change_seconds": 15,
      "predicted_next_status": "GREEN",
              "location": {
    "latitude": 55.755826,
    "longitude": 37.617300
  },

    }
  ]
}
```
### Response Fields:
- `intersection_id` (string) - Identifier for the intersection.
- `timestamp` (ISO 8601 string) - Timestamp of the latest signal reading.
- `traffic_lights` (array) - List of traffic lights at the intersection.

Each traffic light object:
- `light_id` (string) - Unique identifier for the traffic light.
- `current_status` (string) - Current signal state (`RED` or `GREEN`).
- `time_to_next_change_seconds` (integer) - Estimated seconds until the next signal change.
- `predicted_next_status` (string) - Expected next signal state (`RED` or `GREEN`).
- `location` (object) - GPS coordinates of the traffic light.
    - `latitude` (float)
    - `longitude` (float)
- [ ] Docker with Mosquitto
- [ ] Script that listens to Mosquitto and stores telemetry in a database
- [ ] Script that aggregates distinct channels of light for specific traffic lights
- [ ] Backend that retrieves the latest traffic light status
- [ ] Script that calculates the prediction of the next traffic light change

