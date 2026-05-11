# Orion V2 — Distributed IoT Control Platform

Full-stack IoT automation platform for real-time HVAC and irrigation control using Python, React, Raspberry Pi, ESP32, MQTT, and REST APIs.

Orion V2 connects a local application server, Raspberry Pi field controllers, and ESP32 edge nodes to monitor live device state, execute hardware commands, synchronize schedules, track faults, and support AI-assisted automation decisions.

---

## Screenshots

### AI-Assisted Automation

![Orion AI Recommendation](docs/screenshots/orion-ai-recommendation.jpg)

Orion monitors live system state and provides automation recommendations based on weather, device status, and safety rules.

### Live Device Dashboard

![Orion Device Dashboard](docs/screenshots/orion-device-dashboard.jpg)

The dashboard displays real-time weather, irrigation scheduling, HVAC state, telemetry, and device health from the distributed system.

---

## What This Project Demonstrates

Orion V2 demonstrates real-world software and control-system engineering across:

- Full-stack application development
- Backend API design
- Real-time telemetry
- Distributed device coordination
- Hardware relay control
- MQTT messaging
- Raspberry Pi field services
- ESP32 edge-node integration
- HVAC safety logic
- Irrigation scheduling
- Fault detection and monitoring
- AI-assisted automation
- System reliability and debugging

Unlike a simulated dashboard, Orion controls and monitors real hardware.

---

## Architecture

Orion V2 is split into three major layers.

```txt
┌──────────────────────────────────────┐
│          Application Server           │
│  React Dashboard + Flask API + AI     │
└───────────────────┬──────────────────┘
                    │
          REST / MQTT / Telemetry
                    │
┌───────────────────▼──────────────────┐
│        Raspberry Pi Controllers       │
│   HVAC Service + Irrigation Service   │
└───────────────────┬──────────────────┘
                    │
                 MQTT
                    │
┌───────────────────▼──────────────────┐
│             ESP32 Edge Nodes          │
│     Relays + Sensors + Heartbeats     │
└──────────────────────────────────────┘