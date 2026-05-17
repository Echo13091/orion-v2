# Orion V2 — Distributed Edge Automation Platform

Orion V2 is a local-first distributed edge automation platform for real HVAC, irrigation, and environmental vision hardware.

The system runs on NVIDIA Jetson edge hardware and uses Docker Compose to orchestrate the main application services:

- Next.js dashboard
- Flask backend API
- Mosquitto MQTT broker
- AI-assisted monitoring and recommendation loop
- environmental vision node proxy

Orion integrates with Raspberry Pi field controllers, ESP32 relay nodes, and a Raspberry Pi Zero 2 W environmental camera node using REST APIs, MQTT messaging, WebRTC video streaming, and distributed health monitoring.

Unlike a simulated dashboard, Orion interacts with real physical systems and exposes live operational state, hardware faults, environmental context, and safe manual controls through one unified dashboard.

---

## Overview

Orion V2 combines full-stack software, embedded systems, real-time telemetry, Dockerized deployment, WebRTC streaming, and AI-assisted operational monitoring into a single edge automation platform.

Current integrated subsystems:

- HVAC controller
- irrigation controller
- environmental vision node

Current platform capabilities:

- Docker Compose deployment on NVIDIA Jetson
- Next.js operational dashboard
- Flask backend API
- Mosquitto MQTT broker
- local AI-assisted monitoring loop
- HVAC controller integration
- sprinkler / irrigation controller integration
- environmental camera integration
- embedded WebRTC stream inside the Orion dashboard
- browser recording and snapshot controls
- IMX708 autofocus control
- Raspberry Pi field-controller layer
- Raspberry Pi Zero 2 W vision-node layer
- ESP32 relay-node layer
- live telemetry and heartbeat monitoring
- weather-aware irrigation decisions
- fault detection and recovery visibility
- manual, automatic, and autonomous monitoring modes
- persistent runtime state
- real hardware control

Orion is designed as a practical full-stack, embedded, IoT, and edge automation system built around real hardware.

---

## What Orion Demonstrates

Orion V2 demonstrates engineering across multiple layers:

- distributed system architecture
- full-stack application development
- real-time telemetry and monitoring
- MQTT-based device communication
- REST API integration
- WebRTC video streaming
- Raspberry Pi field-controller integration
- Raspberry Pi Zero 2 W camera-node integration
- IMX708 camera integration
- ESP32 embedded node integration
- HVAC and irrigation automation
- environmental monitoring
- Dockerized edge deployment
- container orchestration with Docker Compose
- fault detection and operational visibility
- AI-assisted operational recommendations
- NVIDIA Jetson edge deployment
- safety-focused control logic
- hardware/software integration
- Linux and systemd service deployment

---

## Screenshots

### AI-Assisted Automation

![Orion AI Recommendation](docs/screenshots/orion-ai-recommendation.jpg)

Orion evaluates live telemetry, weather conditions, and device state to provide operational recommendations.

### Live Device Dashboard

![Orion Device Dashboard](docs/screenshots/orion-device-dashboard.jpg)

The dashboard displays HVAC state, irrigation scheduling, environmental camera status, weather data, and distributed system health.

### Healthy Distributed System State

![Healthy system state](docs/screenshots/fault-dashboard-healthy.jpeg)

The dashboard displays healthy controller and node communication across the distributed platform.

### Distributed Fault Detection

![Distributed fault detection](docs/screenshots/fault-dashboard-node-fault.jpeg)

A thermostat field controller was intentionally powered down to validate Orion's ability to detect an offline device, surface the fault condition, and preserve visibility into the remaining system state.

---

## System Architecture

```txt
┌──────────────────────────────────────────────────────────┐
│                  NVIDIA Jetson Edge Server               │
│                                                          │
│  Docker Compose                                          │
│  ├── Next.js Dashboard                                   │
│  ├── Flask Backend API                                   │
│  ├── Mosquitto MQTT Broker                               │
│  └── AI-Assisted Monitoring / Recommendation Loop        │
└───────────────────────────┬──────────────────────────────┘
                            │
              REST / MQTT / WebRTC Signaling
                            │
┌───────────────────────────▼──────────────────────────────┐
│              Raspberry Pi Field Controllers              │
│                                                          │
│  ├── HVAC Controller Service                             │
│  ├── Irrigation Controller Service                       │
│  └── Local Runtime State + Safety Logic                  │
└───────────────────────────┬──────────────────────────────┘
                            │
                           MQTT
                            │
┌───────────────────────────▼──────────────────────────────┐
│                    ESP32 Edge Nodes                      │
│          Relays + Sensors + Heartbeats + Feedback        │
└───────────────────────────┬──────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────┐
│                    Real Equipment                        │
│              HVAC Hardware + Irrigation Hardware         │
└──────────────────────────────────────────────────────────┘


┌──────────────────────────────────────────────────────────┐
│             Raspberry Pi Zero 2 W Vision Node            │
│                                                          │
│  ├── IMX708 Environmental Camera                         │
│  ├── Picamera2                                           │
│  ├── WebRTC Stream Service                               │
│  ├── Autofocus Control                                   │
│  ├── Snapshot Endpoint                                   │
│  ├── Browser Recording Support                           │
│  ├── Health / Fault Status API                           │
│  └── systemd Recovery                                    │
└───────────────────────────┬──────────────────────────────┘
                            │
                   REST + WebRTC Signaling
                            │
┌───────────────────────────▼──────────────────────────────┐
│                  Orion Dashboard                         │
│       Embedded Environmental Camera Stream + Telemetry   │
└──────────────────────────────────────────────────────────┘
```

Orion separates high-level monitoring and orchestration from field-level hardware execution.

The Jetson hosts the main application layer. Raspberry Pi field controllers manage device behavior and safety logic close to the equipment. ESP32 nodes handle relay-level control, telemetry, heartbeat publishing, and failsafe behavior. The Raspberry Pi Zero 2 W vision node provides environmental video and camera telemetry as a first-class subsystem.

---

## Integrated Subsystems

Orion currently integrates three major hardware-facing subsystems:

```txt
HVAC Node
Irrigation Node
Environmental Vision Node
```

Each subsystem exposes operational state, health information, and fault visibility to the Orion dashboard.

### HVAC Node

The HVAC controller provides:

- live temperature telemetry
- humidity telemetry
- cooling / heating state
- fan state
- relay feedback
- sensor status
- heartbeat monitoring
- fault detection
- safety timing logic

### Irrigation Node

The irrigation controller provides:

- zone scheduling
- manual zone control
- active run status
- weather-aware skip logic
- local schedule ownership
- ESP32 relay-node integration
- heartbeat monitoring
- fault visibility

### Environmental Vision Node

The environmental vision node provides:

- live WebRTC video stream
- embedded Orion dashboard viewer
- auto-connect stream behavior
- browser recording controls
- snapshot support
- IMX708 autofocus control
- lens position telemetry
- frame freshness tracking
- online/offline state
- fault visibility
- systemd-managed recovery on the Pi Zero 2 W

---

## Orion Vision Node

The Orion Vision Node is an environmental camera subsystem built around a Raspberry Pi Zero 2 W and an IMX708 camera module.

The node runs independently as a systemd-managed service on the Pi Zero 2 W and exposes local APIs for status, focus control, snapshots, camera restart, and WebRTC stream negotiation.

The Jetson-hosted Orion backend proxies the vision node through `/v1/vision/*` API routes, allowing the main Orion dashboard to display camera health, telemetry, snapshots, focus controls, and the embedded WebRTC stream.

### Current Vision Node Features

- Raspberry Pi Zero 2 W camera node
- IMX708 camera support
- Picamera2 camera stack
- live WebRTC video stream
- embedded stream inside Orion dashboard
- auto-connect stream behavior
- browser-side recording
- snapshot capture
- autofocus once command
- continuous autofocus support
- camera restart command
- camera health telemetry
- stream client count
- frame freshness tracking
- lens position reporting
- online/offline state
- fault visibility
- systemd service recovery

### Vision Node Dashboard Fields

The Orion dashboard displays:

- camera online state
- stream readiness
- current FPS
- stream resolution
- focus mode
- connected clients
- recording state
- lens position
- last-frame freshness
- fault status
- node identifier
- embedded live WebRTC stream

### Orion Backend Vision Routes

```txt
GET  /v1/vision/status
GET  /v1/vision/snapshot
POST /v1/vision/focus
POST /v1/vision/restart-camera
POST /v1/vision/offer
```

### Vision Node Local Routes

```txt
GET  /api/status
GET  /api/state
GET  /api/settings
POST /api/settings
POST /api/camera/focus
POST /api/camera/restart
GET  /api/snapshot
POST /offer
```

### Vision Node Environment Variables

The Orion backend uses the following Docker environment variables to locate the vision node:

```txt
VISION_NODE_URL=http://192.168.7.238:5000
VISION_TIMEOUT=3.0
```

Example Docker Compose backend environment section:

```yaml
environment:
  VISION_NODE_URL: http://192.168.7.238:5000
  VISION_TIMEOUT: "3.0"
```

### Future Vision AI Direction

The vision node is intentionally lightweight. It handles camera capture, WebRTC streaming, focus control, status, and snapshots. Heavier analysis is intended to run on the Jetson.

Planned future capabilities include:

- auto tracking
- digital zoom
- lawn / grass condition monitoring
- irrigation verification through snapshots
- environmental event logging
- AI-assisted outdoor condition summaries
- integration with watering restrictions and weather conditions

---

## Dockerized Edge Deployment

Orion V2 can run as a Docker Compose stack on NVIDIA Jetson hardware.

Current containerized services:

```txt
orion-frontend   Next.js dashboard
orion-backend    Flask API + AI monitoring loop
orion-mqtt       Mosquitto MQTT broker
```

Example startup:

```bash
docker compose up -d
```

Example status check:

```bash
docker ps
```

Expected exposed services:

```txt
Frontend: http://<JETSON-IP>:3001
Backend:  http://<JETSON-IP>:5001
MQTT:     <JETSON-IP>:1883
```

Useful Docker commands:

```bash
docker compose build
docker compose up -d
docker compose logs -f
docker compose restart
docker compose down
```

The Jetson runs the dashboard, backend, AI monitoring loop, and MQTT broker. Raspberry Pi controllers, ESP32 nodes, and the Pi Zero vision node continue handling hardware-facing logic close to the equipment.

This makes Orion easier to restart, reproduce, deploy, and document compared to running each service manually.

---

## Engineering Summary

Orion V2 demonstrates the ability to design and build a complete distributed automation platform that combines frontend development, backend APIs, embedded systems, hardware control, environmental vision, WebRTC streaming, AI-assisted decision logic, Dockerized deployment, and real-world fault handling.

This project goes beyond a normal dashboard demo. Orion monitors real hardware, tracks live device state, uses AI-assisted recommendations, detects offline nodes, handles weather-aware irrigation decisions, displays environmental camera state, and separates manual control from automatic execution.

Key engineering areas:

- full-stack application development
- Python backend development
- Flask API design
- React / Next.js frontend development
- TypeScript dashboard development
- REST API integration
- WebRTC stream integration
- browser recording support
- local AI / LLM integration
- Raspberry Pi field-controller design
- Raspberry Pi Zero 2 W camera-node design
- ESP32 embedded node integration
- MQTT-based device communication
- hardware relay control
- camera hardware integration
- real-time telemetry
- system health monitoring
- fault detection
- persistent state management
- safety-aware automation
- distributed IoT system design
- Linux deployment
- Docker Compose deployment
- systemd service patterns
- edge automation architecture

---

## Core Purpose

Orion V2 was built to answer a practical engineering question:

```txt
Can a local edge automation platform monitor real devices, understand system state, detect hardware problems, stream environmental context, and recommend safer actions before controlling equipment?
```

Orion is designed around that goal.

It does not blindly execute commands. It monitors system state, detects faults, displays recommendations, streams environmental camera data, and gives the user visibility into what the automation layer is doing.

---

## What Makes Orion Different

Many home automation projects are simple dashboards or relay toggles.

Orion V2 is different because it combines:

- real hardware control
- live device status
- environmental vision
- embedded WebRTC camera streaming
- AI-assisted recommendations
- manual and automatic execution modes
- fault-aware behavior
- weather-aware irrigation logic
- system health monitoring
- field-controller separation
- persistent state
- Dockerized edge deployment
- local-first architecture

The result is closer to a small distributed control platform than a basic home automation script.

---

## Main Components

### NVIDIA Jetson Application Server

The NVIDIA Jetson hosts the main Orion platform.

It includes:

- Docker Compose deployment
- React / Next.js dashboard
- Python Flask backend
- Mosquitto MQTT broker
- REST API endpoints
- AI orchestration layer
- session and memory handling
- global system state
- device status aggregation
- environmental camera proxy APIs
- weather-aware automation logic

The dashboard provides a live view of system health, device state, environmental camera stream, automation recommendations, and manual controls.

### Orion Backend

The backend is responsible for:

- exposing API endpoints
- collecting system state
- routing device commands
- proxying vision-node status and WebRTC offers
- running AI-assisted decision logic
- storing persistent memory/state
- tracking system health
- coordinating HVAC, sprinkler, and vision integrations
- reporting faults to the dashboard
- running the background monitoring loop

### Orion Frontend

The frontend is responsible for:

- displaying live automation state
- showing system metrics
- showing AI recommendations
- showing HVAC status
- showing sprinkler status
- showing environmental camera status
- embedding the WebRTC camera stream
- providing recording and snapshot controls
- providing manual control inputs
- displaying saved chat sessions
- exposing the assistant interface
- making the system understandable to the user

### MQTT Broker

The MQTT broker handles distributed messaging between the Jetson application server, Raspberry Pi field controllers, and ESP32 edge nodes.

MQTT is used for:

- telemetry publishing
- heartbeat status
- relay state reporting
- fault messages
- controller state updates
- distributed system visibility

### Raspberry Pi Field Controllers

The Raspberry Pi field controllers are responsible for:

- running local control logic
- exposing device APIs
- communicating with ESP32 nodes
- reporting status to Orion
- managing local runtime state
- keeping device control close to the hardware
- maintaining local schedule ownership
- supporting fail-safe operation

Current field controllers include:

- HVAC controller
- irrigation controller

### Raspberry Pi Zero 2 W Vision Node

The Raspberry Pi Zero 2 W vision node is responsible for:

- running the environmental camera service
- controlling the IMX708 camera
- managing WebRTC stream output
- exposing local camera APIs
- reporting live camera state
- handling autofocus commands
- serving snapshots
- supporting browser recording through the dashboard
- recovering through systemd after reboot or service failure

### ESP32 Edge Nodes

The ESP32 nodes are responsible for:

- relay-level control
- sensor telemetry
- MQTT communication
- heartbeat publishing
- relay feedback publishing
- hardware state reporting
- failsafe behavior when communication is lost

---

## Field Controller Independence

HVAC and irrigation controllers are designed to run independently on Raspberry Pi hardware.

Orion provides centralized monitoring, AI-assisted recommendations, and operator control, but each field controller maintains its own local runtime state, scheduling, safety logic, and fail-safe behavior if the central application server is unavailable.

This separation keeps hardware execution close to the equipment and prevents the dashboard or AI layer from becoming a single point of failure.

The environmental vision node follows the same distributed philosophy. Camera capture and stream production run locally on the Pi Zero 2 W, while Orion provides centralized visibility, control, and future AI processing.

---

## Supported Hardware Layers

Orion V2 is designed around this distributed hardware model:

```txt
NVIDIA Jetson Application Server
        ↓
Raspberry Pi Field Controllers
        ↓
ESP32 Nodes
        ↓
Relay Boards / Sensors
        ↓
Real Equipment
```

Environmental vision layer:

```txt
NVIDIA Jetson Application Server
        ↓
Raspberry Pi Zero 2 W Vision Node
        ↓
IMX708 Camera Module
        ↓
Environmental Camera Stream
```

Current hardware integrations include:

- HVAC controller
- sprinkler / irrigation controller
- environmental vision node
- Raspberry Pi field-controller layer
- Raspberry Pi Zero 2 W camera-node layer
- ESP32 relay-node layer
- local network communication
- MQTT messaging
- REST API integration
- WebRTC video streaming
- relay feedback / heartbeat status

---

## Core Features

### Real-Time Monitoring Dashboard

Orion provides a live operational dashboard displaying:

- weather conditions
- HVAC state
- irrigation schedule
- environmental camera stream
- vision node health
- system health
- CPU / memory / GPU monitoring
- automation mode
- AI recommendations
- saved assistant sessions
- device health
- fault state
- controller and node status
- manual controls

### Distributed Device Communication

The platform uses MQTT messaging, REST APIs, and WebRTC signaling between:

- NVIDIA Jetson application server
- Raspberry Pi field controllers
- Raspberry Pi Zero 2 W environmental camera node
- ESP32 edge nodes

This allows Orion to distribute control logic, telemetry, environmental context, and hardware state across multiple independent devices.

### AI-Assisted Recommendations

Orion can evaluate live system state and produce operational recommendations.

Example recommendation:

```json
{
  "action": "delay_irrigation",
  "reason": "Rain likely. Skip or delay the next irrigation run.",
  "confidence": "high"
}
```

The AI layer is not just a chat interface. It can inspect system state, recommend actions, and route approved changes through the control layer instead of directly bypassing safety logic.

The AI recommendation layer is designed to assist automation decisions, not blindly replace deterministic safety logic.

### Manual and Automatic Execution Modes

Orion separates recommendation from execution.

Supported execution modes include:

- manual mode
- automatic mode
- autonomous monitoring
- manual override

This allows Orion to recommend actions while still giving the user control over whether hardware actions should be applied automatically.

### Device Health Monitoring

Orion monitors connected field controllers, device nodes, and the environmental camera node.

Tracked states may include:

- online/offline status
- heartbeat status
- active sprinkler zone
- HVAC mode
- relay feedback
- sensor status
- camera stream status
- frame freshness
- lens position
- controller health
- fault state
- stale data conditions

This helps Orion avoid assuming that hardware is available when a field device is offline.

### Fault Detection

Orion can detect and surface system faults.

Example fault state:

```json
{
  "fault": true,
  "source": "vision",
  "message": "Environmental camera node unreachable",
  "recommended_action": "Check node power, Wi-Fi, or service status"
}
```

When a fault is active, Orion changes the system state and recommendation instead of continuing normal automation blindly.

### Weather-Aware Irrigation

Orion can use weather conditions to influence irrigation behavior.

Example behavior:

```txt
Rain likely
Irrigation delayed
No sprinkler action needed
```

This helps prevent unnecessary watering and demonstrates state-aware automation logic.

### Environmental Vision

Orion can display a live environmental camera stream directly in the dashboard.

Current environmental vision capabilities include:

- live WebRTC stream
- auto-connected dashboard viewer
- browser recording
- snapshots
- autofocus controls
- camera health state
- fault visibility

This adds visual environmental context to the same platform that already monitors HVAC, irrigation, weather, and hardware state.

---

## HVAC Automation

The HVAC controller supports:

- live temperature and humidity telemetry
- auto / cool / heat / off modes
- fan auto / on / off modes
- compressor protection logic
- minimum equipment on/off timers
- changeover lockout handling
- fan post-run handling
- relay feedback monitoring
- active alarm visibility
- fault reporting
- controller health state

A major reliability improvement separates commanded HVAC state from relay feedback so stale node data cannot incorrectly re-command equipment.

HVAC state may include:

- current temperature
- humidity
- mode
- setpoint
- cooling state
- heating state
- fan state
- relay feedback
- DHT sensor health
- node heartbeat
- fault state

The HVAC controller can run independently or integrate with Orion for centralized visibility.

---

## Irrigation Automation

The irrigation controller supports:

- multi-zone sprinkler scheduling
- manual zone control
- live irrigation timeline
- safe stop commands
- schedule synchronization
- weather-aware skip logic
- Raspberry Pi local schedule ownership
- ESP32 relay-node integration

Orion can sync weekday schedules, start times, zone durations, and next-run timelines to the Raspberry Pi irrigation controller.

The irrigation controller can continue operating independently on the Raspberry Pi even if the central Orion dashboard becomes unavailable.

Sprinkler state may include:

- online/offline state
- active zone
- running state
- schedule status
- next scheduled run
- weather delay state
- manual command state
- relay feedback
- node heartbeat
- fault state

---

## Environmental Vision Automation

The environmental vision node currently focuses on live visibility, recording, snapshots, and telemetry.

Current supported behavior:

- stream environmental camera video into Orion
- show camera online/offline state
- expose frame freshness
- report stream client count
- display focus mode and lens position
- trigger autofocus once from the dashboard
- restart the camera service path from Orion
- record the embedded browser stream
- capture snapshots through the Orion backend

Planned future behavior:

- detect birds or motion events
- classify bird species
- auto-track and digitally zoom on subjects
- inspect grass condition visually
- compare lawn condition with weather and irrigation state
- support irrigation verification after watering
- combine camera context with water restrictions and weather logic
- generate AI-assisted environmental summaries

---

## Fault Detection and System Visibility

Orion includes fault-aware monitoring for distributed field devices.

The platform can:

- detect offline devices
- surface node-level faults
- report relay mismatches
- report camera-node reachability failures
- display controller health state
- preserve visibility during partial system failures
- support safer troubleshooting and recovery

The system is designed to fail safely, report problems clearly, and maintain operational visibility instead of silently hiding failures.

---

## AI-Assisted Operational Recommendations

Orion includes an AI-assisted monitoring layer capable of evaluating live system state and generating operational recommendations.

Example behaviors include:

- delaying irrigation when rain is likely
- monitoring system health
- explaining current device state
- summarizing telemetry
- recommending operator actions
- inspecting active faults
- explaining why automation is delayed
- routing approved changes through the control layer

Automation can run in manual approval mode or auto-execute mode depending on safety settings.

The environmental vision layer expands the future AI context available to Orion, allowing the Jetson to eventually analyze outdoor conditions, bird activity, lawn state, irrigation effects, and environmental changes.

---

## Reliability Improvements

Recent reliability work included:

- Docker Compose deployment support for the main Orion platform
- containerized frontend, backend, and MQTT broker
- integrated Orion Vision Node environmental camera
- embedded WebRTC stream in the Orion dashboard
- browser recording and snapshot controls
- auto-connect vision stream behavior
- refactored the project into a cleaner public repository structure
- fixed real sprinkler schedule synchronization between Orion and the Raspberry Pi controller
- added safer HVAC state handling so relay feedback cannot incorrectly re-command equipment
- improved frontend rendering for richer live device data
- fixed irrigation timeline zone numbering
- verified live telemetry, hardware state, and schedule execution through the dashboard
- preserved field-controller independence so local Pi services can continue operating without Orion

---

## Reliability and Safety Design

Orion is designed around predictable hardware behavior and operational reliability.

Key reliability concepts include:

- field-controller independence
- local controller ownership of hardware logic
- distributed architecture
- runtime state persistence
- Dockerized application services
- systemd-managed field services
- fault visibility
- camera-node reachability checks
- compressor lockout protection
- minimum equipment on/off timers
- fan post-run handling
- relay feedback monitoring
- manual override capability
- safe stop commands
- weather-aware irrigation protection
- fail-safe controller operation

Important safety goals include:

- do not blindly assume hardware commands succeed
- expose active faults clearly
- separate manual and automatic execution
- avoid running automation when hardware is unavailable
- detect offline field nodes
- show last decision and recommendation
- keep system state visible
- provide manual override behavior
- preserve runtime state where useful
- avoid unsafe automation when device state is unknown

The Raspberry Pi field controllers continue operating locally even if the Jetson application layer becomes unavailable.

The environmental camera node also runs independently as a systemd service so camera visibility can recover automatically after node reboot or service failure.

---

## Technology Stack

### Backend

- Python
- Flask
- REST APIs
- MQTT
- WebRTC offer proxying
- local AI integration
- runtime state management
- device control routing
- system metrics collection
- persistent memory/session storage

### Frontend

- React
- Next.js
- TypeScript
- real-time telemetry polling
- embedded WebRTC viewer
- browser recording controls
- component-based UI architecture
- assistant interface
- saved chat display

### AI / Automation

- local LLM support
- Ollama integration
- structured decision output
- AI-assisted recommendations
- deterministic safety rules
- explainable decision reasons
- automation state loop
- future environmental image analysis

### Hardware and Infrastructure

- NVIDIA Jetson
- Raspberry Pi 4
- Raspberry Pi Zero 2 W
- IMX708 camera module
- ESP32
- Linux
- MQTT messaging
- relay-control hardware
- HVAC equipment integration
- irrigation hardware integration
- environmental camera integration
- local network deployment

### Deployment / Infrastructure

- Docker
- Docker Compose
- NVIDIA Jetson edge deployment
- Mosquitto MQTT broker
- Linux networking
- containerized backend/frontend services
- systemd-managed field-controller services
- systemd-managed camera-node service
- local network deployment

---

## Repository Structure

```txt
server/
├── backend/
│   ├── api/
│   │   ├── system.py
│   │   ├── control.py
│   │   ├── chat.py
│   │   ├── sessions.py
│   │   └── vision.py
│   ├── ai/
│   ├── core/
│   ├── tools/
│   └── app.py
└── frontend/
    └── app/
        └── page.tsx

field-controller/
├── hvac-controller/
└── irrigation-controller/

firmware/
├── esp32-hvac-node/
└── esp32-irrigation-node/

docs/
├── screenshots/

examples/
scripts/
docker-compose.yml
```

---

## Backend API Examples

Orion exposes API routes for system status, sessions, chat, device control, and environmental vision.

Example system endpoint:

```txt
GET /v1/system
```

Example chat/session endpoints:

```txt
GET  /v1/sessions
GET  /v1/session/{id}
POST /v1/chat/stream
```

Example control endpoints:

```txt
GET  /v1/control/help
POST /v1/control/command
POST /v1/control/sprinkler/zone
POST /v1/control/sprinkler/stop
POST /v1/control/sprinkler/program-now
POST /v1/control/thermostat/setpoint
POST /v1/control/thermostat/mode
POST /v1/control/thermostat/fan
```

Example vision endpoints:

```txt
GET  /v1/vision/status
GET  /v1/vision/snapshot
POST /v1/vision/focus
POST /v1/vision/restart-camera
POST /v1/vision/offer
```

These endpoints allow the dashboard, assistant, and automation logic to interact with real device controllers and the environmental camera node.

---

## Example System Status Payload

```json
{
  "ai": "active",
  "fault": false,
  "cpu": 3.4,
  "memory": 16.5,
  "gpu": 0.0,
  "last_decision": {
    "action": "observe",
    "reason": "System stable"
  },
  "sprinkler": {
    "online": true,
    "running": false,
    "active_zone": null
  },
  "hvac": {
    "online": true,
    "mode": "cool",
    "current_temp": 76.6,
    "setpoint": 72
  }
}
```

---

## Example Vision Status Payload

```json
{
  "ok": true,
  "online": true,
  "node_url": "http://192.168.7.238:5000",
  "node_id": "vision_node_1",
  "node_name": "Orion Vision Node",
  "camera_online": true,
  "streaming_clients": 1,
  "recording": false,
  "fps": 13.7,
  "resolution": "1280x720",
  "focus_mode": "auto_once",
  "lens_position": 1.09,
  "last_frame_age": 0.03,
  "fault": false
}
```

---

## Example Fault Payload

```json
{
  "ai": "active",
  "fault": true,
  "automation_state": "Fault",
  "last_decision": {
    "action": "recover",
    "reason": "System fault detected"
  },
  "recommendation": {
    "title": "Investigate fault",
    "reason": "ESP32 sprinkler node offline. Review logs before running automation."
  }
}
```

---

## Example AI Decision Payload

```json
{
  "action": "delay_irrigation",
  "reason": "Rain likelihood is high. Skip or delay the next irrigation run.",
  "params": {
    "rain_likelihood": 100
  },
  "execution": "monitor_only",
  "safety": "no_hardware_action_needed"
}
```

---

## Local LLM Integration

Orion can integrate with a local LLM through Ollama.

Example local model setup:

```txt
Ollama endpoint: http://127.0.0.1:11434
Default model: mistral
Code model: deepseek-coder:6.7b
```

The LLM is used for assisted reasoning and explanations while deterministic safety logic remains responsible for preventing unsafe control behavior.

Example use cases:

- explain current system state
- summarize device faults
- recommend whether to delay irrigation
- classify system state
- produce structured automation decisions
- answer questions through the dashboard assistant
- future environmental camera event summaries

---

## Automation Loop

Orion can run a background automation loop.

Typical loop behavior:

```txt
Read system state
        ↓
Read device telemetry
        ↓
Check weather / hardware status
        ↓
Check vision node status
        ↓
Apply deterministic safety checks
        ↓
Ask AI assistant for recommendation
        ↓
Parse structured decision
        ↓
Update dashboard state
        ↓
Optionally execute approved safe action
```

The automation loop is designed to keep the dashboard updated while preventing unsafe hardware actions.

---

## Manual Control Examples

Example natural command:

```txt
run sprinkler zone 3 for 2 minutes
```

Example thermostat command:

```txt
set thermostat to 72
```

Example assistant prompt:

```txt
Why is irrigation delayed?
```

Example system health prompt:

```txt
Check home system health
```

Example vision interaction:

```txt
Open Orion Vision Node and view the environmental camera stream.
```

---

## Running Locally

### Backend

```bash
cd server/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

On Windows PowerShell:

```powershell
cd server/backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Backend:

```txt
http://127.0.0.1:5001
```

### Frontend

```bash
cd server/frontend
npm install
npm run dev
```

Frontend:

```txt
http://localhost:3000
```

---

## Docker Compose Deployment

The main Orion platform can run on NVIDIA Jetson hardware using Docker Compose.

From the project root:

```bash
docker compose build
docker compose up -d
```

Check running services:

```bash
docker ps
```

View logs:

```bash
docker compose logs -f
```

Restart services:

```bash
docker compose restart
```

Stop services:

```bash
docker compose down
```

Default local deployment ports:

```txt
Frontend: http://<JETSON-IP>:3001
Backend:  http://<JETSON-IP>:5001
MQTT:     <JETSON-IP>:1883
```

The Docker deployment is intended for the main Jetson-hosted platform services. Raspberry Pi field controllers, ESP32 nodes, and the Pi Zero vision node remain hardware-facing components that communicate with the main platform over the local network.

---

## Environment Variables

Example environment variables:

```txt
ORION_BACKEND_URL=http://localhost:5001
NEXT_PUBLIC_BACKEND_URL=http://<JETSON-IP>:5001
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=mistral
WEATHER_LOCATION=Brandon,FL
MQTT_HOST=localhost
MQTT_PORT=1883
VISION_NODE_URL=http://192.168.7.238:5000
VISION_TIMEOUT=3.0
```

Actual variables may vary depending on local, Docker, Jetson, or field-controller deployment.

---

## Field Controllers

The field controllers are designed to run independently on Raspberry Pi hardware using systemd-managed services.

Example controller folders:

```txt
field-controller/hvac-controller/
field-controller/irrigation-controller/
```

Each field controller owns:

- local runtime state
- hardware-facing logic
- scheduling
- safety protections
- MQTT communication
- relay coordination
- fault reporting
- fail-safe behavior

This architecture keeps hardware execution close to the equipment while Orion provides centralized monitoring and operational visibility.

---

## Vision Node Deployment Notes

The Orion Vision Node currently runs on a Raspberry Pi Zero 2 W using a systemd service.

Example role:

```txt
Raspberry Pi Zero 2 W
        ↓
Runs Orion Vision Node service
        ↓
Captures IMX708 camera stream
        ↓
Serves WebRTC stream + status API
        ↓
Orion backend proxies stream/status into dashboard
```

Recommended operational notes:

- reserve the Pi Zero IP address in the router
- keep the vision node on the same LAN as the Jetson
- use systemd so the camera node starts after reboot
- keep AI processing on the Jetson rather than the Pi Zero
- use the Pi Zero as a lightweight camera and telemetry node

---

## Field Controller Repositories

Orion V2 is supported by separate field-controller repositories.

### HVAC Field Controller

```txt
Orion V2 — Raspberry Pi ESP32 HVAC Controller
```

This controller handles local HVAC dashboard control, MQTT communication, ESP32 relay-node integration, DHT telemetry, safety timing, relay feedback, and fault detection.

### Sprinkler Field Controller

```txt
Orion V2 — Raspberry Pi ESP32 Sprinkler Controller
```

This controller handles local sprinkler scheduling, manual zone control, persistent schedules, runtime state tracking, ESP32 relay-node integration, MQTT communication, and safety-aware irrigation control.

---

## Deployment Notes

Orion supports both development and edge deployment workflows.

### Jetson Application Deployment

The main Orion platform can run on NVIDIA Jetson hardware using Docker Compose.

Containerized services include:

- frontend dashboard
- backend API
- MQTT broker
- AI-assisted monitoring loop
- vision-node backend proxy

### Field Controller Deployment

The Raspberry Pi field controllers are designed to run independently using systemd-managed services.

This keeps hardware-facing logic close to the equipment while the Jetson provides centralized monitoring, AI-assisted recommendations, and dashboard visibility.

### Vision Node Deployment

The environmental vision node runs independently on Raspberry Pi Zero 2 W using a systemd-managed service.

This keeps camera capture and stream generation local to the camera hardware while Orion handles dashboard integration, recording controls, snapshots, and future AI processing.

Example deployment options:

- Windows PC for development
- NVIDIA Jetson for the main edge application server
- Raspberry Pi for field-controller services
- Raspberry Pi Zero 2 W for environmental vision
- ESP32 nodes for relay control
- local network with MQTT broker
- systemd services for long-running controller processes

The architecture is intentionally distributed so device control can remain close to the hardware while the dashboard and AI supervisor provide higher-level visibility.

---

## Jetson / Edge Deployment

Orion can be deployed on an edge compute device such as an NVIDIA Jetson.

Benefits of edge deployment include:

- local AI capability
- lower dependency on cloud services
- compact dedicated hardware
- always-on dashboard/backend host
- containerized service deployment
- stronger edge-compute deployment model
- centralized supervisor for distributed field nodes

Example edge deployment role:

```txt
Jetson / edge server
        ↓
Runs Docker Compose stack
Runs Orion backend
Runs Orion frontend
Runs Mosquitto MQTT broker
Runs AI-assisted monitoring loop
Monitors Raspberry Pi field controllers
Monitors Pi Zero environmental camera node
Receives MQTT/device telemetry
Displays dashboard and AI recommendations
```

---

## Project Relevance

Orion V2 demonstrates the ability to build a complete connected system across multiple layers:

- frontend dashboard
- backend API
- AI-assisted automation
- WebRTC video integration
- Raspberry Pi field controllers
- Raspberry Pi Zero camera node
- ESP32 hardware nodes
- MQTT communication
- Docker Compose deployment
- device telemetry
- environmental camera telemetry
- relay control
- persistent state
- fault handling
- safety-aware decision logic
- local edge deployment

This makes the project relevant to full-stack development, IoT engineering, embedded systems, automation, edge AI, backend API development, computer vision infrastructure, and control-system integration.

---

## Reliability Goals

Planned and current reliability goals include:

- persistent state recovery
- controller health monitoring
- heartbeat checks
- stale telemetry detection
- field-node offline detection
- vision-node offline detection
- relay feedback validation
- frame freshness monitoring
- fault history
- automatic recovery attempts
- systemd service recovery for field controllers
- systemd service recovery for the vision node
- safe manual override
- deterministic safety checks before execution

---

## Current Status

Working features:

- Docker Compose deployment on NVIDIA Jetson
- containerized frontend, backend, and MQTT broker
- Orion dashboard
- backend API
- assistant interface
- saved chat/session support
- live system metrics
- AI-assisted recommendation display
- manual and automatic execution mode display
- autonomous monitoring state
- HVAC integration support
- sprinkler integration support
- environmental vision node integration
- embedded WebRTC camera stream
- browser recording for vision stream
- snapshot support
- autofocus control
- weather-aware irrigation logic
- fault state display
- Raspberry Pi field-controller integration
- Raspberry Pi Zero 2 W camera-node integration
- ESP32 node integration support
- local LLM support
- Jetson edge deployment support
- distributed MQTT messaging

In progress / planned:

- stronger automated recovery behavior
- more detailed event history
- expanded MQTT topic documentation
- improved controller reconciliation
- cached vision-node status optimization
- persistent Docker volumes
- MQTT authentication
- better deployment documentation
- fault recovery demo clips
- improved fault timeline visualization
- additional screenshots and demo clips
- architecture diagrams
- hardware simulation mode
- Jetson AI vision analysis

---

## Future Improvements

Planned improvements include:

- persistent event log viewer
- fault history timeline
- improved AI decision audit trail
- command acknowledgment tracking
- controller heartbeat dashboard
- cached vision-node status endpoint
- AI-assisted camera event summaries
- bird detection
- bird species recognition
- auto tracking and digital zoom
- grass condition monitoring
- watering restriction awareness
- irrigation verification from environmental snapshots
- automated recovery workflows
- stronger weather integration
- mobile dashboard polish
- production Docker hardening
- persistent Docker volumes
- MQTT authentication
- nginx reverse proxy
- dashboard authentication
- improved setup documentation
- test coverage for backend routes
- hardware simulation mode
- public demo video
- clearer architecture diagrams

---

## Where Orion V2 Can Grow

Orion V2 is currently focused on HVAC, irrigation, and environmental vision, but the architecture is designed to expand into a broader edge automation platform.

The same distributed pattern — NVIDIA Jetson application layer, Raspberry Pi field controllers, Raspberry Pi camera nodes, ESP32 edge nodes, MQTT messaging, REST APIs, WebRTC streaming, real-time telemetry, fault tracking, and AI-assisted operational recommendations — can support additional real-world systems such as:

- environmental monitoring
- lighting control
- pump and motor systems
- energy management
- security and sensor networks
- distributed equipment supervision
- predictive maintenance workflows
- remote edge-device coordination
- wildlife monitoring
- lawn and irrigation intelligence

The long-term goal is to evolve Orion into a scalable edge AI and industrial IoT platform capable of monitoring, coordinating, and automating multiple physical systems from a unified operational dashboard.

The platform is intentionally modular so additional field controllers, edge nodes, camera nodes, telemetry pipelines, and automation services can be integrated without redesigning the overall system architecture.

---

## Project Story

Orion V2 started as a practical home automation project and grew into a distributed edge automation platform.

The system connects real HVAC, irrigation, and environmental camera hardware to a central dashboard, adds field-controller separation, integrates ESP32 relay nodes, embeds a WebRTC vision node, and layers AI-assisted recommendations on top of deterministic safety logic.

The project demonstrates practical engineering across software, hardware, networking, automation, video streaming, AI-assisted monitoring, and system design.

---

## Related Repositories

Recommended GitHub project structure:

```txt
orion-v2
Main platform, dashboard, backend API, AI supervisor, environmental vision integration

raspberry-pi-esp32-hvac-controller
HVAC field-controller layer

raspberry-pi-esp32-sprinkler-controller
Irrigation field-controller layer
```

Together, these repositories show the full distributed system:

```txt
Main Orion platform
        ↓
HVAC field controller
        ↓
Sprinkler field controller
        ↓
Vision node
        ↓
ESP32 hardware nodes
        ↓
Real equipment and environmental camera hardware
```

---

## Security Notes

The current deployment is intended for local network / development use.

Important security considerations before exposing Orion outside a private LAN:

- do not expose MQTT publicly without authentication
- do not expose the vision node publicly
- do not port-forward the dashboard or backend without access control
- add dashboard authentication before remote access
- add MQTT username/password and ACLs
- use HTTPS / reverse proxy for external access
- keep hardware control endpoints protected
- keep camera endpoints protected
- avoid running on public Wi-Fi without additional security hardening

Orion is currently designed as a local-first edge automation system.

---

## Safety Notes

This project interacts with real electrical, HVAC, irrigation, and camera hardware.

Important safety considerations:

- understand wiring before connecting relays
- use proper relay isolation
- verify voltage levels
- avoid unsafe HVAC short-cycling
- provide manual shutoff methods
- test with disconnected loads first
- do not rely only on software for emergency shutoff
- follow safe electrical practices
- use camera hardware responsibly
- use at your own risk

Orion is an educational engineering project, not a certified commercial control system.

---

## License

This project is provided as an educational engineering project.

Use at your own risk when controlling real hardware.

---

## Author

David Echols  
GitHub: Echo13091

Built as a distributed edge automation project combining AI-assisted software, NVIDIA Jetson edge compute, Docker Compose deployment, Raspberry Pi field controllers, Raspberry Pi Zero 2 W environmental vision, ESP32 hardware nodes, and real home automation equipment.
