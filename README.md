\# Orion V2 — Distributed AI-Assisted IoT Control Platform



Orion V2 is a distributed IoT automation platform using a Windows-hosted application server, Raspberry Pi field controllers, and ESP32 edge nodes for real-world HVAC and irrigation control.



The platform combines:



\- Real-time monitoring

\- Distributed device communication

\- Hardware relay control

\- AI-assisted orchestration

\- Persistent system state

\- Safety and lockout logic

\- Frontend dashboard visualization

\- Modular backend services



\---



\# Architecture



Orion V2 is split into three layers:



\## 1. Application Server



The Windows server hosts:



\- React/Next.js dashboard

\- Flask backend API

\- AI orchestration layer

\- Global system state

\- Session and memory management

\- Device coordination



\## 2. Field Controller Layer



The Raspberry Pi field controller handles:



\- HVAC control services

\- Irrigation control services

\- MQTT communication

\- Hardware safety logic

\- Fail-safe recovery

\- Local runtime state



\## 3. Edge Hardware Layer



ESP32 nodes provide:



\- Relay control

\- Sensor monitoring

\- Heartbeat publishing

\- Edge-level hardware interaction

\- Distributed device communication



\---



\# Technologies



\## Backend



\- Python

\- Flask

\- MQTT

\- REST APIs

\- Local AI integration



\## Frontend



\- Next.js

\- React

\- TypeScript



\## Hardware / Infrastructure



\- Raspberry Pi 4

\- ESP32

\- MQTT messaging

\- systemd services

\- Relay control systems



\---



\# Features



\- Distributed architecture

\- Real-time monitoring dashboard

\- HVAC relay control

\- Irrigation automation

\- AI-assisted orchestration

\- Weather-aware automation logic

\- Persistent runtime state

\- Device heartbeat monitoring

\- Safety lockouts and cooldown logic

\- Modular backend tooling

\- Session and memory tracking



\---



\# Repository Structure



```txt

server/

├── backend/

└── frontend/



field-controller/

├── hvac-controller/

└── irrigation-controller/



firmware/

├── esp32-hvac-node/

└── esp32-irrigation-node/

```



\---



\# Status



Orion V2 is an actively developed distributed control platform focused on real-world automation reliability, modular system design, and scalable edge-device integration.

