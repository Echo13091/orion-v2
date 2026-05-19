import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from providers.thermostat_manager import get_thermostat_state


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

STATE_FILE = Path(os.getenv("ORION_THERMOSTAT_STATE_FILE", DATA_DIR / "thermostats.json"))
EVENT_FILE = Path(os.getenv("ORION_THERMOSTAT_EVENT_FILE", DATA_DIR / "thermostat_events.json"))

STALE_AFTER_SECONDS = int(os.getenv("ORION_THERMOSTAT_STALE_AFTER_SECONDS", "180"))


DEFAULT_THERMOSTAT = {
    "id": "t6pro_living_room",
    "name": "RPi4 / ESP32 HVAC Thermostat",
    "type": "thermostat",
    "vendor": "Orion Field Controller",
    "model": "Raspberry Pi 4 + ESP32 Relay Node",
    "source": "orion_existing_hvac",
    "online": False,
    "status": "offline",
    "temperature": None,
    "humidity": None,
    "cool_setpoint": None,
    "heat_setpoint": None,
    "target_setpoint": None,
    "mode": "off",
    "fan_mode": "auto",
    "equipment_state": "idle",
    "heating": False,
    "cooling": False,
    "fan_active": False,
    "last_update": None,
    "last_update_age_seconds": None,
    "fault": True,
    "fault_code": "thermostat_offline",
    "fault_message": "No thermostat telemetry has been received yet.",
    "supervisory_control_enabled": False,
    "last_command": None,
}


def _now() -> float:
    return time.time()


def _load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text())
    except Exception:
        return fallback


def _save_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def _ensure_state() -> Dict[str, Dict[str, Any]]:
    state = _load_json(STATE_FILE, {})
    if not isinstance(state, dict):
        state = {}

    if DEFAULT_THERMOSTAT["id"] not in state:
        state[DEFAULT_THERMOSTAT["id"]] = dict(DEFAULT_THERMOSTAT)
        _save_json(STATE_FILE, state)

    return state


def _events() -> List[Dict[str, Any]]:
    events = _load_json(EVENT_FILE, [])
    return events if isinstance(events, list) else []


def _save_events(events: List[Dict[str, Any]]) -> None:
    _save_json(EVENT_FILE, events[-250:])


def log_event(
    thermostat_id: str,
    event: str,
    severity: str = "info",
    message: str = "",
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    record = {
        "timestamp": _now(),
        "thermostat_id": thermostat_id,
        "event": event,
        "severity": severity,
        "message": message,
        "details": details or {},
    }

    events = _events()
    events.append(record)
    _save_events(events)

    return record


def normalize_thermostat(raw: Dict[str, Any]) -> Dict[str, Any]:
    thermostat_id = raw.get("id") or raw.get("thermostat_id") or "t6pro_living_room"

    temp = raw.get("temperature", raw.get("temp", raw.get("current_temp", raw.get("current_temperature"))))
    humidity = raw.get("humidity", raw.get("current_humidity"))

    cool_setpoint = raw.get("cool_setpoint", raw.get("setpoint", raw.get("target_temp_high")))
    heat_setpoint = raw.get("heat_setpoint", raw.get("target_temp_low"))
    target_setpoint = raw.get(
        "target_setpoint",
        raw.get("setpoint", raw.get("target_temperature", cool_setpoint)),
    )

    mode = raw.get("mode", raw.get("hvac_mode", raw.get("system_mode", "off")))
    fan_mode = raw.get("fan_mode", raw.get("fan", "auto"))
    equipment_state = raw.get("equipment_state", raw.get("hvac_action", raw.get("hvac_state", "idle")))

    equipment_state = str(equipment_state).lower()

    heating = bool(raw.get("heating", raw.get("heating_active", equipment_state == "heating")))
    cooling = bool(raw.get("cooling", raw.get("cooling_active", equipment_state == "cooling")))
    fan_active = bool(raw.get("fan_active", raw.get("fan_on", raw.get("fan", False))))

    online = bool(raw.get("online", raw.get("node_online", True)))
    now = _now()

    thermostat = {
        "id": thermostat_id,
        "name": raw.get("name", "RPi4 / ESP32 HVAC Thermostat"),
        "type": "thermostat",
        "vendor": raw.get("vendor", "Orion Field Controller"),
        "model": raw.get("model", "Raspberry Pi 4 + ESP32 Relay Node"),
        "source": raw.get("source", "orion_existing_hvac"),
        "online": online,
        "status": "online" if online else "offline",
        "temperature": temp,
        "humidity": humidity,
        "cool_setpoint": cool_setpoint,
        "heat_setpoint": heat_setpoint,
        "target_setpoint": target_setpoint,
        "mode": mode,
        "fan_mode": fan_mode,
        "equipment_state": equipment_state,
        "heating": heating,
        "cooling": cooling,
        "fan_active": fan_active,
        "hold": raw.get("hold"),
        "battery": raw.get("battery"),
        "last_update": now,
        "last_update_age_seconds": 0,
        "fault": not online,
        "fault_code": "" if online else "thermostat_offline",
        "fault_message": "" if online else "Thermostat is offline.",
        "supervisory_control_enabled": bool(raw.get("supervisory_control_enabled", False)),
        "last_command": raw.get("last_command"),
    }

    return thermostat


def refresh_health(thermostat: Dict[str, Any]) -> Dict[str, Any]:
    last_update = thermostat.get("last_update")
    now = _now()

    if not last_update:
        thermostat["online"] = False
        thermostat["status"] = "offline"
        thermostat["last_update_age_seconds"] = None
        thermostat["fault"] = True
        thermostat["fault_code"] = "thermostat_offline"
        thermostat["fault_message"] = "No thermostat telemetry has been received yet."
        return thermostat

    age = int(now - float(last_update))
    thermostat["last_update_age_seconds"] = age

    if age > STALE_AFTER_SECONDS:
        thermostat["online"] = False
        thermostat["status"] = "stale"
        thermostat["fault"] = True
        thermostat["fault_code"] = "thermostat_stale"
        thermostat["fault_message"] = f"Thermostat telemetry is stale. Last update was {age} seconds ago."
    else:
        thermostat["online"] = bool(thermostat.get("online", True))
        thermostat["status"] = "online" if thermostat["online"] else "offline"

        if thermostat["online"]:
            thermostat["fault"] = False
            thermostat["fault_code"] = ""
            thermostat["fault_message"] = ""

    return thermostat


def list_thermostats() -> List[Dict[str, Any]]:
    state = _ensure_state()
    updated = {}

    for thermostat_id, thermostat in state.items():
        updated[thermostat_id] = refresh_health(thermostat)

    _save_json(STATE_FILE, updated)
    return list(updated.values())


def get_thermostat(thermostat_id: str) -> Optional[Dict[str, Any]]:
    state = _ensure_state()
    thermostat = state.get(thermostat_id)

    if not thermostat:
        return None

    thermostat = refresh_health(thermostat)
    state[thermostat_id] = thermostat
    _save_json(STATE_FILE, state)

    return thermostat


def update_thermostat(raw: Dict[str, Any]) -> Dict[str, Any]:
    state = _ensure_state()
    thermostat = normalize_thermostat(raw)
    thermostat_id = thermostat["id"]

    previous = state.get(thermostat_id)
    state[thermostat_id] = thermostat
    _save_json(STATE_FILE, state)

    if not previous or previous.get("status") != thermostat.get("status"):
        log_event(
            thermostat_id,
            "status_change",
            "info",
            f"Thermostat status changed to {thermostat.get('status')}.",
            {
                "previous_status": previous.get("status") if previous else None,
                "new_status": thermostat.get("status"),
            },
        )

    return thermostat


def request_setpoint_change(
    thermostat_id: str,
    setpoint: float,
    mode: Optional[str] = None,
    source: str = "orion_dashboard",
    reason: str = "Manual Orion setpoint request",
) -> Dict[str, Any]:
    thermostat = get_thermostat(thermostat_id)

    if not thermostat:
        raise KeyError(f"Unknown thermostat: {thermostat_id}")

    if setpoint < 50 or setpoint > 90:
        raise ValueError("Setpoint must be between 50°F and 90°F.")

    command = {
        "timestamp": _now(),
        "action": "setpoint_change_requested",
        "thermostat_id": thermostat_id,
        "setpoint": setpoint,
        "mode": mode or thermostat.get("mode"),
        "source": source,
        "reason": reason,
        "executed": False,
        "execution_status": "pending_integration",
        "message": "Command recorded. Real thermostat write integration is not enabled yet.",
    }

    state = _ensure_state()
    thermostat["last_command"] = command
    thermostat["target_setpoint"] = setpoint

    if mode:
        thermostat["mode"] = mode

    state[thermostat_id] = thermostat
    _save_json(STATE_FILE, state)

    log_event(
        thermostat_id,
        "setpoint_change_requested",
        "info",
        f"Setpoint change requested: {setpoint}°F.",
        command,
    )

    return {
        "ok": True,
        "thermostat": thermostat,
        "command": command,
    }


def recent_events(limit: int = 25) -> List[Dict[str, Any]]:
    return list(reversed(_events()))[:limit]


def sync_from_provider() -> Dict[str, Any]:
    provider_state = get_thermostat_state()

    thermostat = update_thermostat({
        "id": provider_state.get("id", "t6pro_living_room"),
        "name": provider_state.get("name", "Orion Thermostat"),
        "vendor": provider_state.get("vendor", "Unknown"),
        "model": provider_state.get("model", "Unknown"),
        "source": provider_state.get("provider", "unknown"),
        "online": provider_state.get("online", False),
        "temperature": provider_state.get("temperature"),
        "humidity": provider_state.get("humidity"),
        "target_setpoint": provider_state.get("setpoint"),
        "mode": provider_state.get("mode"),
        "fan_mode": provider_state.get("fan_mode"),
        "equipment_state": provider_state.get("equipment_state"),
        "cooling": provider_state.get("cooling"),
        "heating": provider_state.get("heating"),
        "fan_active": provider_state.get("fan"),
        "raw": provider_state,
    })

    return thermostat
