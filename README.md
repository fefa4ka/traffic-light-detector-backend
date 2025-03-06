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

## Mapping Channels to Traffic Lights
To determine the current state of a traffic light, the backend groups related channels under a single traffic light entity.

For example:
- If `Channel 1` (Red light A) is active and `Channel 2` (Green light A) is inactive → Traffic light A is RED.
- If `Channel 1` (Red light A) is inactive and `Channel 2` (Green light A) is active → Traffic light A is GREEN.

The same rules apply to other traffic lights. These mappings allow the system to infer the active state of a complete intersection.

## Recognizing Channels for RED and GREEN Signals
Each traffic light has two channels mapped to it: one for the RED signal and one for the GREEN signal. The mapping follows predefined bit masks stored in the database.

### Channel Mapping in Database:
- The `traffic_light_channels` table defines which bit masks correspond to RED or GREEN signals for each traffic light.
- RED and GREEN channels are distinguished by their numerical bitmask values.

### Example:
| light_id | channel_mask | signal_color |
|----------|-------------|--------------|
| 1        | 1           | RED          |
| 1        | 2           | GREEN        |
| 2        | 4           | RED          |
| 2        | 8           | GREEN        |

### Identification Logic:
1. The active channels from telemetry data are read.
2. The system checks `traffic_light_channels` to match channels with signal colors.
3. If `channel_mask` with `signal_color='RED'` is active, the light is RED; if `signal_color='GREEN'` is active, the light is GREEN.

## Database Implementation for Channel Mapping
The backend uses an SQLite database to track traffic lights and their corresponding channels. This ensures efficient storage and retrieval of telemetry data.

### Table Structure:
- `traffic_lights`: Stores traffic light metadata, including location and intersection association.
- `traffic_light_channels`: Maps individual channel bitmasks to specific traffic lights.

### Example Table Definitions:
```sql
CREATE TABLE traffic_lights (
    light_id INTEGER PRIMARY KEY AUTOINCREMENT,
    intersection_id TEXT NOT NULL,
    description TEXT
);

CREATE TABLE traffic_light_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    light_id INTEGER NOT NULL,
    channel_mask INTEGER NOT NULL,
    FOREIGN KEY (light_id) REFERENCES traffic_lights(light_id)
);
```

### How it Works:
1. Incoming telemetry messages contain a bitmask representing active channels.
2. The system queries `traffic_light_channels` to find which traffic lights correspond to the active channels.
3. The aggregated state is stored and used for determining the overall traffic condition at an intersection.

## Grouping Traffic Lights into an Intersection
Each intersection consists of multiple traffic lights, which need to be grouped logically. The backend associates traffic lights based on predefined intersection identifiers.

- Traffic lights sharing the same intersection ID are considered part of the same intersection.
- The system aggregates all traffic lights at an intersection to derive a complete view of signal states.

Example:
- `intersection_001` contains:
  - `tl_001_a`: Main road north-south direction
  - `tl_001_b`: Main road east-west direction
  - `tl_001_c`: Pedestrian crossing north-south
  - `tl_001_d`: Pedestrian crossing east-west

This allows for a structured representation of the traffic conditions at a given location.

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
The `id` field is a unique identifier for the traffic light detector.

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


## Implementation Plan

1. **MQTT Broker Setup**  
   - [x] Deploy a Mosquitto MQTT broker to receive telemetry from traffic lights.

2. **Telemetry Listener**  
   - Implement a service that subscribes to MQTT topics and stores received messages in a database.

3. **Traffic Light Aggregation**  
   - Develop a script to process raw telemetry and group light signals into logical traffic lights.

4. **Backend API**  
   - Build a REST API to provide real-time traffic light statuses.

5. **Prediction Module**  
   - Implement an algorithm to estimate the next expected light change timing from stored data.

6. **Deployment and Monitoring**  
   - Containerize services, configure logging, and ensure system reliability.

