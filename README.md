# Orion V2 — Distributed Edge Automation Platform

Orion V2 is a local-first distributed edge automation platform for real HVAC, irrigation, weather, thermostat, and environmental vision hardware.

It runs on NVIDIA Jetson edge hardware using Docker Compose and integrates with Raspberry Pi field controllers, ESP32 relay nodes, MQTT telemetry, REST APIs, WebRTC video streaming, deterministic environmental logic, and AI-assisted operational recommendations.

Orion is not a simulated dashboard. It monitors and coordinates real physical systems.

---

## Highlights

- NVIDIA Jetson edge deployment
- Docker Compose orchestration
- Next.js / React / TypeScript dashboard
- Python Flask backend API
- Mosquitto MQTT broker
- Raspberry Pi HVAC and irrigation field controllers
- ESP32 relay / telemetry nodes
- Raspberry Pi Zero 2 W environmental vision node
- IMX708 camera integration
- WebRTC environmental camera streaming
- browser recording and snapshot controls
- visual lawn condition analysis
- visual rain / wet-surface evidence detection
- weather-aware irrigation decisions
- thermostat / HVAC node detail page
- sprinkler / irrigation detail page
- weather intelligence detail page
- supervisory decision center
- fault-aware monitoring
- manual and automatic execution modes
- local-first architecture

---

## Screenshots

### Main Operations Dashboard

![Orion Main Dashboard](docs/screenshots/orion-main-dashboard.jpeg)

The main dashboard provides a clean command overview for live system health, current recommendations, subsystem status, automation mode, and assistant interaction.

### Environmental Vision Node

![Orion Vision Node](docs/screenshots/orion-vision-node.jpeg)

The Vision page embeds the live environmental camera stream and displays camera health, lawn condition, visual rain evidence, weather context, and irrigation impact.

### Irrigation Controller

![Orion Sprinkler Node](docs/screenshots/orion-sprinkler-node.jpeg)

The Sprinkler page shows live irrigation state, active zone status, relay activity, schedule context, and weather-aware recommendations.

### Weather Intelligence

![Orion Weather Intelligence](docs/screenshots/orion-weather-intelligence.jpeg)

The Weather page shows outdoor conditions, rain probability, forecast context, and how weather affects automation decisions.

### Supervisory Decision Engine

![Orion Decision Center](docs/screenshots/orion-decision-center.jpeg)

The Decision Center displays the current recommendation, decision trace, safety gating, automation mode, command result, and raw decision state.

### Thermostat / HVAC Node

![Orion Thermostat Node](docs/screenshots/orion-thermostat-node.jpeg)

The Thermostat page normalizes live HVAC state from the RPi4 / ESP32 controller and exposes setpoints, cooling state, fan state, humidity, event history, and command logging.

---

## What Orion Demonstrates

Orion demonstrates engineering across multiple layers:

- full-stack application development
- backend API design
- distributed system architecture
- Dockerized edge deployment
- MQTT-based device communication
- REST API integration
- WebRTC stream integration
- browser-side media recording
- embedded hardware integration
- Raspberry Pi field-controller design
- ESP32 relay-node integration
- HVAC automation
- irrigation automation
- camera-assisted environmental monitoring
- deterministic visual analysis
- weather-aware decision logic
- AI-assisted recommendation workflows
- fault detection and operational visibility
- safety-aware hardware control

The goal is to show a complete edge automation platform, not a simple relay dashboard.

---

## System Architecture

```txt
┌────────────────────────────────────────────────────────────┐
│                 NVIDIA Jetson Edge Server                  │
│                                                            │
│  Docker Compose                                            │
│  ├── Next.js Frontend                                      │
│  ├── Flask Backend API                                     │
│  ├── Mosquitto MQTT Broker                                 │
│  ├── Thermostat Bridge                                     │
│  ├── Environmental Decision Engine                         │
│  └── AI-Assisted Monitoring Loop                           │
└───────────────────────────┬────────────────────────────────┘
                            │
                  REST / MQTT / WebRTC
                            │
┌───────────────────────────▼────────────────────────────────┐
│              Raspberry Pi Field Controllers                │
│                                                            │
│  ├── HVAC Controller Service                               │
│  ├── Irrigation Controller Service                         │
│  └── Local Runtime State + Safety Logic                    │
└───────────────────────────┬────────────────────────────────┘
                            │
                           MQTT
                            │
┌───────────────────────────▼────────────────────────────────┐
│                    ESP32 Edge Nodes                        │
│                                                            │
│  Relays + Sensors + Heartbeats + Feedback                  │
└───────────────────────────┬────────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────────┐
│                    Real Equipment                          │
│                                                            │
│  HVAC Equipment + Irrigation Hardware                      │
└────────────────────────────────────────────────────────────┘
```

Environmental vision runs as a separate distributed subsystem:

```txt
┌────────────────────────────────────────────────────────────┐
│              Raspberry Pi Zero 2 W Vision Node             │
│                                                            │
│  ├── IMX708 Camera                                         │
│  ├── Picamera2                                             │
│  ├── WebRTC Stream Service                                 │
│  ├── Snapshot Endpoint                                     │
│  ├── Autofocus Control                                     │
│  ├── Lawn Condition Analysis                               │
│  ├── Visual Rain / Wet-Surface Detection                   │
│  └── Health / Fault API                                    │
└───────────────────────────┬────────────────────────────────┘
                            │
                   REST + WebRTC Signaling
                            │
┌───────────────────────────▼────────────────────────────────┐
│                    Orion Backend                           │
│                                                            │
│  Proxies vision status, snapshots, analysis, and stream     │
│  negotiation into the Orion dashboard.                     │
└────────────────────────────────────────────────────────────┘
```

---

## Dashboard Structure

Orion separates the main command dashboard from detailed subsystem views.

```txt
/
├── /decision-center
├── /vision
├── /weather
├── /sprinkler
└── /thermostat
```

The main dashboard provides a high-level operational overview. Each subsystem page provides deeper engineering visibility.

### Main Dashboard

The dashboard shows:

- overall system health
- AI status
- automation mode
- current recommendation
- execution control
- subsystem summaries
- assistant interface
- saved chats
- raw system snapshot

### Decision Center

The Decision Center shows:

- current recommendation
- action source
- decision trace
- safety context
- manual vs automatic execution mode
- command result
- raw decision JSON

### Vision Node

The Vision page shows:

- live WebRTC camera feed
- stream status
- camera health
- FPS and resolution
- focus state
- lens position
- frame freshness
- visual lawn condition
- visual rain / wet-surface evidence
- weather context
- environmental recommendation

### Sprinkler Node

The Sprinkler page shows:

- irrigation status
- active zone
- next scheduled run
- relay activity
- controller health
- schedule state
- weather-aware decision
- upcoming zone timeline
- raw controller JSON

### Weather Intelligence

The Weather page shows:

- outdoor temperature
- feels-like temperature
- humidity
- rain probability
- wind speed
- forecast context
- automation impact
- environmental reasoning

### Thermostat Node

The Thermostat page shows:

- room temperature
- target setpoint
- humidity
- equipment state
- cooling / heating / fan activity
- HVAC mode
- fan mode
- event history
- command logging

---

## Integrated Subsystems

### HVAC / Thermostat Node

The HVAC controller provides:

- live temperature telemetry
- humidity telemetry
- setpoint state
- cooling / heating state
- fan state
- relay feedback
- safety timing logic
- heartbeat monitoring
- fault visibility

The thermostat detail page normalizes HVAC state into a first-class Orion subsystem. Today it can read from the RPi4 / ESP32 HVAC controller. The same model can support future Honeywell / Resideo thermostat integration.

### Irrigation Node

The irrigation controller provides:

- multi-zone scheduling
- manual zone control
- active run status
- relay state
- local schedule ownership
- weather-aware skip logic
- heartbeat monitoring
- fault visibility

The sprinkler detail page displays zone timelines, relay activity, schedule state, and weather-aware recommendations.

### Environmental Vision Node

The Vision node provides:

- live environmental video
- WebRTC streaming
- browser recording
- snapshot capture
- autofocus control
- frame freshness telemetry
- lawn condition analysis
- visual rain / wet-surface evidence
- camera health status
- fault state

### Environmental Decision Engine

The decision engine combines:

- weather conditions
- rain probability
- camera rain evidence
- visual lawn condition
- dryness index
- sprinkler runtime state
- next scheduled irrigation
- low-light analysis availability

Example recommendation:

```txt
Delay irrigation
```

Example reason:

```txt
Rain probability is high and the environmental camera shows rain or wet-surface evidence.
Delay irrigation and continue monitoring lawn condition.
```

The decision engine is deterministic and advisory. Hardware action requires approval unless explicitly configured for safe automatic execution.

---

## AI-Assisted Monitoring

Orion includes an AI-assisted monitoring layer that can inspect live system state and explain recommendations.

The AI layer can:

- summarize current system health
- explain why irrigation is delayed
- inspect live device telemetry
- describe active faults
- answer dashboard questions
- support structured recommendations

The AI does not bypass deterministic safety logic. Hardware actions are routed through the control layer.

---

## Docker Deployment

Orion runs as a Docker Compose stack on the Jetson.

Current services:

```txt
orion-frontend            Next.js dashboard
orion-backend             Flask API + monitoring loop
orion-mqtt                Mosquitto MQTT broker
orion-thermostat-bridge   HVAC state normalization bridge
```

Start the stack:

```bash
docker compose up -d --build
```

Check status:

```bash
docker compose ps
```

View logs:

```bash
docker compose logs -f
```

Default ports:

```txt
Frontend: http://<JETSON-IP>:3001
Backend:  http://<JETSON-IP>:5001
MQTT:     <JETSON-IP>:1883
```

---

## API Examples

### System State

```txt
GET /v1/system
```

### Vision

```txt
GET  /v1/vision/status
GET  /v1/vision/snapshot
GET  /v1/vision/grass-condition
GET  /v1/vision/rain-detection
POST /v1/vision/focus
POST /v1/vision/restart-camera
POST /v1/vision/offer
```

### Thermostats

```txt
GET  /v1/thermostats
GET  /v1/thermostats/{id}
POST /v1/thermostats/ingest
POST /v1/thermostats/{id}/setpoint
GET  /v1/thermostats/events
```

### Control

```txt
POST /v1/control/sprinkler/zone
POST /v1/control/sprinkler/stop
POST /v1/control/sprinkler/program-now
POST /v1/control/thermostat/setpoint
POST /v1/control/thermostat/mode
POST /v1/control/thermostat/fan
POST /v1/control/ai/mode
POST /v1/control/ai/execute
```

### Assistant / Sessions

```txt
GET  /v1/sessions
GET  /v1/session/{id}
POST /v1/chat/stream
```

---

## Example System Payload

```json
{
  "ai_status": "active",
  "automation_mode": "manual",
  "fault": null,
  "weather": {
    "online": true,
    "temp": 85.0,
    "rain_chance": 100
  },
  "sprinkler": {
    "online": true,
    "running": false,
    "next_run": "6:00 AM · 10 min"
  },
  "thermostat": {
    "online": true,
    "temperature": 75.4,
    "setpoint": 72,
    "cooling": true,
    "fan": true
  },
  "environment": {
    "recommendation": "delay_irrigation",
    "confidence": "high",
    "reason": "Rain probability is high. Delay irrigation and continue monitoring."
  }
}
```

---

## Technology Stack

### Frontend

- Next.js
- React
- TypeScript
- WebRTC viewer
- subsystem detail pages
- live polling
- assistant interface

### Backend

- Python
- Flask
- REST APIs
- MQTT integration
- system state aggregation
- device control routing
- vision proxy routes
- thermostat normalization
- environmental decision engine

### Infrastructure

- NVIDIA Jetson
- Docker
- Docker Compose
- Mosquitto MQTT
- Linux
- local network deployment

### Hardware

- Raspberry Pi 4 field controllers
- Raspberry Pi Zero 2 W vision node
- IMX708 camera
- ESP32 relay nodes
- HVAC equipment
- irrigation equipment

### AI / Automation

- local LLM support
- Ollama integration
- deterministic safety logic
- AI-assisted explanations
- structured recommendations
- manual / automatic execution modes

---

## Field Controller Independence

HVAC and irrigation controllers are designed to run independently on Raspberry Pi hardware.

Orion provides centralized monitoring, AI-assisted recommendations, and operator control, but each field controller maintains its own local runtime state, scheduling, safety logic, and fail-safe behavior if the central Jetson application server is unavailable.

This separation keeps hardware execution close to the equipment and prevents the dashboard or AI layer from becoming a single point of failure.

---

## Reliability and Safety Design

Orion is designed around predictable hardware behavior and operational reliability.

Key reliability concepts include:

- field-controller independence
- local controller ownership of hardware logic
- Dockerized application services
- systemd-managed field services
- runtime state persistence
- fault visibility
- stale telemetry detection
- camera-node reachability checks
- visual condition telemetry
- low-light analysis handling
- compressor lockout protection
- minimum equipment on/off timers
- fan post-run handling
- relay feedback monitoring
- manual override capability
- safe stop commands
- weather-aware irrigation protection

Important safety goals include:

- do not blindly assume hardware commands succeed
- expose active faults clearly
- separate recommendation from execution
- avoid running automation when hardware is unavailable
- detect offline field nodes
- show last decision and recommendation
- provide manual override behavior
- avoid unsafe automation when device state is unknown
- avoid treating low-light visual analysis as reliable lawn data

Orion is an educational engineering project and is not a certified commercial control system.

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

## Environment Variables

Example environment variables:

```txt
NEXT_PUBLIC_BACKEND_URL=http://<JETSON-IP>:5001
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=mistral
WEATHER_LOCATION=Brandon,FL
MQTT_HOST=localhost
MQTT_PORT=1883
VISION_NODE_URL=http://192.168.7.238:5000
VISION_TIMEOUT=5.0
ORION_THERMOSTAT_SYNC_INTERVAL_SECONDS=10
```

Actual values may vary depending on local, Docker, Jetson, or field-controller deployment.

---

## Repository Structure

```txt
server/
├── backend/
│   ├── api/
│   ├── ai/
│   ├── core/
│   ├── routes/
│   ├── tools/
│   ├── app.py
│   ├── thermostat_service.py
│   └── thermostat_bridge.py
└── frontend/
    └── app/
        ├── page.tsx
        ├── decision-center/
        ├── sprinkler/
        ├── thermostat/
        ├── thermostats/
        ├── vision/
        └── weather/

docs/
├── screenshots/

docker-compose.yml
docker-compose.override.yml
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

## Current Status

Working features:

- Docker Compose deployment on NVIDIA Jetson
- containerized frontend, backend, MQTT broker, and thermostat bridge
- clean main operations dashboard
- dedicated subsystem detail pages
- assistant interface
- saved chat/session support
- live system metrics
- AI-assisted recommendation display
- environmental decision engine
- manual and automatic execution mode display
- HVAC integration support
- thermostat state normalization
- sprinkler integration support
- environmental vision node integration
- embedded WebRTC camera stream
- browser recording for vision stream
- snapshot support
- autofocus control
- visual lawn condition analysis
- visual rain / wet-surface evidence detection
- low-light lawn analysis handling
- weather-aware irrigation logic
- fault state display
- Raspberry Pi field-controller integration
- Raspberry Pi Zero 2 W camera-node integration
- ESP32 node integration support
- local LLM support
- Jetson edge deployment support
- distributed MQTT messaging

Planned improvements:

- persistent event log viewer
- fault history timeline
- improved AI decision audit trail
- command acknowledgment tracking
- controller heartbeat dashboard
- improved lawn-region targeting and calibration
- watering restriction awareness
- irrigation verification from environmental snapshots
- automated recovery workflows
- production Docker hardening
- persistent Docker volumes
- MQTT authentication
- dashboard authentication
- reverse proxy / HTTPS
- public demo video
- hardware simulation mode

---

## Project Relevance

Orion V2 demonstrates the ability to build a complete connected system across multiple layers:

- frontend dashboard
- backend API
- AI-assisted automation
- WebRTC video integration
- visual analysis
- environmental decision logic
- Raspberry Pi field controllers
- Raspberry Pi Zero camera node
- ESP32 hardware nodes
- MQTT communication
- Docker Compose deployment
- device telemetry
- relay control
- persistent state
- fault handling
- safety-aware decision logic
- local edge deployment

This makes the project relevant to full-stack development, IoT engineering, embedded systems, automation, edge AI, backend API development, computer vision infrastructure, and control-system integration.

---

## Author

David Echols  
GitHub: Echo13091

Built as a distributed edge automation project combining AI-assisted software, NVIDIA Jetson edge compute, Docker Compose deployment, Raspberry Pi field controllers, Raspberry Pi Zero 2 W environmental vision, ESP32 hardware nodes, and real home automation equipment.
