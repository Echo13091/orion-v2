# Orion V2 — Distributed Edge Automation Platform

![Orion CI](https://github.com/Echo13091/orion-v2/actions/workflows/ci.yml/badge.svg)

Orion V2 is a local-first supervisory automation platform for real HVAC, irrigation, thermostat, weather, environmental vision, and distributed edge-control systems.

It runs on NVIDIA Jetson edge hardware using Docker Compose and integrates Raspberry Pi field controllers, ESP32 relay nodes, MQTT telemetry, Flask APIs, a Next.js operations dashboard, MJPEG / snapshot-based environmental video, deterministic safety logic, event history, and AI-assisted operational recommendations.

This is not a simulated dashboard. Orion supervises real distributed hardware, normalizes telemetry, exposes degraded subsystem state, records command and decision history, tracks state transitions, and routes hardware actions through safe operator-approved control paths.

---

## Project Summary

Orion demonstrates a full-stack edge automation system built around real equipment behavior instead of mock data. The platform separates field-controller responsibility from supervisory orchestration: local controllers own hardware execution and safety timing, while Orion provides centralized visibility, decision support, fault awareness, event history, and operator control.

Core engineering themes:

- distributed system supervision
- hardware-adjacent backend APIs
- real-time telemetry normalization
- degraded-state handling
- safety-aware command routing
- event and fault visibility
- edge deployment on Linux / NVIDIA Jetson
- full-stack operational UI design

---

## At a Glance

| Area | Implementation |
|---|---|
| Edge host | NVIDIA Jetson running Docker Compose |
| Frontend | Next.js, React, TypeScript |
| Backend | Python Flask API |
| Messaging | Mosquitto MQTT |
| Field controllers | Raspberry Pi HVAC and irrigation controllers |
| Edge nodes | ESP32 relay / telemetry nodes |
| Vision node | Raspberry Pi Zero 2 W, IMX708 camera, MJPEG stream, snapshot endpoint |
| Vision interpretation | Jetson-side lawn, rain / wet-surface, and low-light analysis |
| AI layer | Local LLM-assisted monitoring and recommendations |
| Control model | Deterministic safety logic with operator-approved execution |
| Operations layer | Event timeline, active faults, audit trail, and state transitions |

---

## Table of Contents

- [Project Summary](#project-summary)
- [Purpose](#purpose)
- [Highlights](#highlights)
- [Screenshots](#screenshots)
- [What Orion Demonstrates](#what-orion-demonstrates)
- [System Architecture](#system-architecture)
- [Dashboard Structure](#dashboard-structure)
- [Integrated Subsystems](#integrated-subsystems)
- [AI-Assisted Monitoring](#ai-assisted-monitoring)
- [Operations Console](#operations-console)
- [Degraded Subsystem Handling](#degraded-subsystem-handling)
- [Supervisory Orchestration Focus](#supervisory-orchestration-focus)
- [Quick Start](#quick-start)
- [Docker Deployment](#docker-deployment)
- [API Examples](#api-examples)
- [Event Model](#event-model)
- [Technology Stack](#technology-stack)
- [Field Controller Independence](#field-controller-independence)
- [Reliability and Safety Design](#reliability-and-safety-design)
- [Running Locally](#running-locally)
- [Environment Variables](#environment-variables)
- [Quality Gates](#quality-gates)
- [Repository Structure](#repository-structure)
- [Security Notes](#security-notes)
- [Safety Notes](#safety-notes)
- [Current Status](#current-status)
- [Project Relevance](#project-relevance)
- [Author](#author)
- [Licensing](#licensing)


## Purpose

Orion V2 was built to explore how a local edge platform can supervise distributed automation systems while keeping field controllers independent, visible, and safe.

Instead of replacing device-level logic, Orion acts as a supervisory orchestration layer above HVAC, irrigation, thermostat, weather, and environmental vision subsystems.

The goal is to demonstrate a complete edge automation platform, not a simple relay dashboard.

Orion is designed around one central idea: real automation systems need more than commands. They need state visibility, fault awareness, safe execution paths, operational history, state transitions, command audit trails, and clear reasoning about why an action should or should not happen.

---

## Highlights

### Platform

- NVIDIA Jetson edge deployment
- Docker Compose orchestration
- Next.js / React / TypeScript dashboard
- Python Flask backend API
- Mosquitto MQTT broker
- Local-first LAN architecture

### Field Systems

- Raspberry Pi HVAC and irrigation controllers
- ESP32 relay / telemetry nodes
- Thermostat state normalization
- Sprinkler scheduling, manual control, and weather-aware skip logic
- Environmental vision node with IMX708 camera, MJPEG live view, and snapshot endpoint

### Operations and Reliability

- Operations Console for events, faults, node health, and command evidence
- Degraded subsystem visibility
- Compacted repeated-event timeline
- Manual command audit events
- Automation policy decision events
- Environmental decision evidence events
- Irrigation state transition history
- Controller acknowledgement normalization
- Optional hardware-control token gate
- Single-process threaded backend deployment for predictable local runtime state

### Decision Support

- Environmental decision engine
- Structured evidence model for trusted, ignored, and blocked inputs
- Decision Center evidence view
- Operations audit trail for environmental decision evidence changes
- Rain / wet-surface evidence handling
- Low-light visual-analysis safeguards
- Local LLM-assisted monitoring and recommendations
- Manual and automatic execution modes with deterministic safety checks

---

## Screenshots

### Main Operations Dashboard

![Orion Main Dashboard](docs/screenshots/orion-main-dashboard.jpeg)

Clean command overview for system health, recommendations, subsystem status, automation mode, and assistant interaction.

### Environmental Vision Node

![Orion Vision Node](docs/screenshots/orion-vision-node.jpeg)

Live environmental camera stream with camera health, lawn condition, visual rain evidence, weather context, and irrigation impact.

### Operations Console — Degraded Subsystem Handling

![Orion Operations Console](docs/screenshots/orion-operations-console.jpeg)

Operations view showing degraded subsystem state, active faults, compacted repeated events, node health, operational impact messages, and continued operation with trusted telemetry.

### Irrigation Controller

![Orion Sprinkler Node](docs/screenshots/orion-sprinkler-node.jpeg)

Live irrigation state, active zone status, relay activity, schedule context, and weather-aware recommendations.

### Weather Intelligence

![Orion Weather Intelligence](docs/screenshots/orion-weather-intelligence.jpeg)

Outdoor conditions, rain probability, forecast context, and automation impact.

### Supervisory Decision Center

![Orion Decision Center](docs/screenshots/orion-decision-center.jpeg)

Current recommendation, decision trace, safety gating, automation mode, command result, trusted evidence, ignored inputs, blockers, and raw decision state.

### Thermostat / HVAC Node

![Orion Thermostat Node](docs/screenshots/orion-thermostat-node.jpeg)

Normalized HVAC state from the RPi4 / ESP32 controller, including setpoint, cooling state, fan state, humidity, event history, and command logging.

---

## What Orion Demonstrates

Orion demonstrates engineering across multiple layers:

- full-stack application development
- backend API design
- distributed system architecture
- Dockerized edge deployment
- MQTT-based device communication
- REST API integration
- MJPEG / snapshot-based camera integration
- browser-side media workflows
- embedded hardware integration
- Raspberry Pi field-controller design
- ESP32 relay-node integration
- HVAC automation
- irrigation automation
- environmental camera monitoring
- deterministic visual analysis
- weather-aware decision logic
- structured decision evidence modeling
- AI-assisted recommendation workflows
- fault detection and operational visibility
- safety-aware hardware control

The goal is to demonstrate a complete edge automation platform, not a simple relay dashboard.

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
                  REST / MQTT / MJPEG / Snapshots
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

Environmental vision runs as a separate subsystem:

```txt
┌────────────────────────────────────────────────────────────┐
│              Raspberry Pi Zero 2 W Vision Node             │
│                                                            │
│  ├── IMX708 Camera                                         │
│  ├── Picamera2                                             │
│  ├── MJPEG Stream                                          │
│  ├── Snapshot Endpoint                                     │
│  ├── Camera Health / Status API                            │
│  └── systemd Runtime                                       │
└───────────────────────────┬────────────────────────────────┘
                            │
                    REST / MJPEG Integration
                            │
┌───────────────────────────▼────────────────────────────────┐
│                    Orion / Jetson Platform                 │
│                                                            │
│  Displays live environmental video and evaluates vision     │
│  context such as lawn condition, rain / wet-surface         │
│  evidence, low-light analysis availability, and trusted     │
│  decision evidence.                                        │
└────────────────────────────────────────────────────────────┘
```

---

## Dashboard Structure

Orion separates the main command dashboard from detailed subsystem views.

```txt
/
├── /decision-center
├── /operations
├── /vision
├── /vision-node
├── /weather
├── /sprinkler
└── /thermostat
```

The main dashboard provides a high-level operational overview. Each subsystem page provides deeper engineering visibility. The Operations Console provides event history, active faults, command audit records, policy decisions, evidence changes, and state transitions.

### Main Dashboard

The dashboard shows:

- overall system health
- AI status
- automation mode
- current recommendation
- execution controls
- subsystem summaries
- Operations Console entry point
- assistant interface
- saved chats
- raw system snapshot

### Decision Center

The Decision Center shows:

- current recommendation
- action source
- decision trace
- trusted decision evidence
- ignored / degraded inputs
- blockers
- safety context
- manual vs automatic execution mode
- command result
- raw decision JSON

Decision Center recommendations are recorded into the Operations event history when they represent meaningful policy decisions, safety decisions, evidence changes, manual override pauses, or recommended actions.

### Operations Console

The Operations Console shows:

- event timeline
- degraded subsystem panel
- active faults
- node health
- automation policy decisions
- environmental decision evidence changes
- manual command audit events
- state transition history
- execution evidence
- controller acknowledgements
- operational impact messages
- compacted repeated events
- quick filters for faults, vision, automation, manual commands, and transitions

Example Operations events:

```txt
Vision node unreachable
Environmental recommendation is delay_irrigation (high) with usable evidence
Manual run zone 6 for 1 minute(s)
Manual sprinkler stop
irrigation transitioned from idle to manual_zone_running
irrigation transitioned from manual_zone_running to idle
Rain likely (100%). Next irrigation run is already skipped; no sprinkler output is active.
```

### Vision Node

The Vision page shows:

- live MJPEG camera feed
- stream status
- direct field-node access
- camera health
- FPS and resolution
- frame freshness
- Jetson-side lawn condition interpretation
- Jetson-side rain / wet-surface evidence evaluation
- Low-light / dark-condition handling
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

The thermostat detail page normalizes HVAC state into a first-class Orion subsystem. Today it reads from the RPi4 / ESP32 HVAC controller. The same normalized model can support future Honeywell / Resideo thermostat integration.

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

The sprinkler detail page displays zone timelines, relay activity, schedule state, controller status, and weather-aware recommendations.

The Operations Console records irrigation command audit events and state transitions, for example:

```txt
Manual run zone 6 for 1 minute(s)
irrigation transitioned from idle to manual_zone_running
Manual sprinkler stop
irrigation transitioned from manual_zone_running to idle
```

### Environmental Vision Node

The Vision subsystem provides:

- live environmental video from the Raspberry Pi Zero 2 W camera node
- MJPEG streaming
- snapshot capture
- frame freshness telemetry
- camera health status
- fault state
- Jetson-side lawn condition interpretation
- Jetson-side rain / wet-surface evidence evaluation
- low-light handling so unreliable visual readings are not treated as valid lawn data

When the vision node is unreachable, Orion records a structured `node_offline` event into the Operations Console.

### Environmental Decision Engine

The environmental decision engine combines:

- weather conditions
- rain probability
- physical rain-sensor state
- controller health
- camera rain evidence
- visual lawn condition
- dryness index
- sprinkler runtime state
- next scheduled irrigation
- low-light analysis availability
- trusted / ignored / blocked evidence classification

Example recommendation:

```txt
Delay irrigation
```

Example reason:

```txt
Rain probability is high and trusted controller evidence shows irrigation should be delayed.
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

## Degraded Subsystem Handling

Orion is designed to keep operating when a subsystem becomes unavailable.

When the environmental vision node is offline, Orion does not treat missing camera data as valid visual evidence. The Vision page enters a degraded mode and clearly marks camera-derived information as unavailable.

In degraded vision mode:

- camera stream is unavailable
- snapshots are unavailable
- lawn analysis is unavailable
- visual rain and wet-surface evidence are unavailable
- weather and controller telemetry remain active
- environmental recommendations continue using trusted available inputs
- unavailable sensor data is not treated as valid evidence

The Operations Console surfaces degraded subsystem state as first-class operational information. Repeated events such as `Vision node unreachable` are compacted into a single timeline card with repeat count, first-seen time, latest-seen time, latest evidence, and operational impact.

Example compacted Operations timeline entry:

- Event: Vision node unreachable
- Repeat count: x11
- First seen: May 22, 9:53 PM
- Latest: May 23, 1:42 PM
- Impact: camera stream, snapshots, lawn condition, and visual rain evidence are unavailable.
- Fallback: Orion continues operating with weather, sprinkler, thermostat, and event telemetry.

This keeps the timeline readable while preserving the operational history and evidence trail.

---

## Supervisory Orchestration Focus

Orion is designed as a supervisory orchestration layer, not a monolithic replacement for every controller.

Field controllers remain responsible for local device behavior, safety timing, and hardware execution. Orion provides centralized visibility, normalized telemetry, recommendations, command routing, fault awareness, and operator control.

This architecture allows Orion to supervise multiple device types and protocols over time:

- existing Raspberry Pi controllers
- ESP32 relay nodes
- thermostat integrations
- MQTT devices
- REST-connected services
- future RS485 / Modbus devices
- environmental camera nodes

The important design goal is normalization: different hardware backends can feed one consistent Orion model.

---

## Quick Start

For a Jetson-based deployment:

```bash
