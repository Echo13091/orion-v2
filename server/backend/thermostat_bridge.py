#!/usr/bin/env python3
import json
import os
import time
import urllib.request

SYSTEM_URL = os.getenv("ORION_SYSTEM_URL", "http://backend:5001/v1/system")
INGEST_URL = os.getenv("ORION_THERMOSTAT_INGEST_URL", "http://backend:5001/v1/thermostats/ingest")
SYNC_INTERVAL_SECONDS = int(os.getenv("ORION_THERMOSTAT_SYNC_INTERVAL_SECONDS", "10"))


def read_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as res:
        return json.loads(res.read().decode("utf-8"))


def post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=5) as res:
        return json.loads(res.read().decode("utf-8"))


def normalize(system: dict) -> dict:
    t = system.get("thermostat") or {}
    raw = t.get("raw") or t

    temp = (
        t.get("temperature")
        or t.get("temp")
        or raw.get("temperature")
        or raw.get("temp")
        or raw.get("current_temp")
    )

    setpoint = t.get("setpoint") or raw.get("setpoint")

    if t.get("cooling") or raw.get("cooling") or raw.get("cooling_active"):
        equipment_state = "cooling"
    elif t.get("heating") or raw.get("heating") or raw.get("heating_active"):
        equipment_state = "heating"
    elif t.get("fan_active") or raw.get("fan_active") or raw.get("fan_on"):
        equipment_state = "fan"
    else:
        equipment_state = "idle"

    return {
        "id": "t6pro_living_room",
        "name": "RPi4 / ESP32 HVAC Thermostat",
        "vendor": "Orion Field Controller",
        "model": "Raspberry Pi 4 + ESP32 Relay Node",
        "source": "orion_existing_hvac",
        "online": bool(t.get("online", raw.get("online", False))),
        "temperature": temp,
        "humidity": t.get("humidity", raw.get("humidity")),
        "target_setpoint": setpoint,
        "cool_setpoint": setpoint,
        "heat_setpoint": raw.get("heat_setpoint", 68),
        "mode": t.get("mode", raw.get("mode", raw.get("system_mode", "auto"))),
        "fan_mode": t.get("fan_mode", raw.get("fan_mode", "auto")),
        "equipment_state": equipment_state,
        "cooling": bool(t.get("cooling", raw.get("cooling", raw.get("cooling_active", False)))),
        "heating": bool(t.get("heating", raw.get("heating", raw.get("heating_active", False)))),
        "fan_active": bool(t.get("fan_active", raw.get("fan_active", raw.get("fan_on", False)))),
    }


def main() -> None:
    print("[thermostat-bridge] starting", flush=True)
    print(f"[thermostat-bridge] system_url={SYSTEM_URL}", flush=True)
    print(f"[thermostat-bridge] ingest_url={INGEST_URL}", flush=True)

    while True:
        try:
            system = read_json(SYSTEM_URL)
            payload = normalize(system)
            result = post_json(INGEST_URL, payload)
            thermostat = result.get("thermostat", {})

            print(
                "[thermostat-bridge] synced "
                f"online={thermostat.get('online')} "
                f"temp={thermostat.get('temperature')} "
                f"setpoint={thermostat.get('target_setpoint')} "
                f"state={thermostat.get('equipment_state')}",
                flush=True,
            )

        except Exception as exc:
            print(f"[thermostat-bridge] sync failed: {exc}", flush=True)

        time.sleep(SYNC_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
