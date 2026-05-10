import os
import time
from copy import deepcopy
from threading import RLock
from typing import Any

_state_lock = RLock()

VALID_AUTOMATION_MODES = {"manual", "auto"}

SPRINKLER_ZONES = int(os.getenv("SPRINKLER_ZONES", "8"))

DEFAULT_IRRIGATION_SCHEDULE = {
    "enabled": True,
    "controller": "sprinkler",
    "orion_controlled": True,
    "sync_mode": "orion",
    "hardware_sync_required": True,
    "hardware_synced": False,
    "hardware_result": None,
    "days": ["mon", "tue", "wed", "thu", "fri"],
    "start_time": "06:00",
    "duration_minutes": 10,
    "zones": list(range(1, SPRINKLER_ZONES + 1)),
    "skip_if_rain_likely": True,
    "skip_next_run": False,
    "skip_reason": None,
    "last_run_at": None,
    "last_run_key": None,
    "last_scheduler_event": None,
    "last_skip_at": None,
    "last_skip_reason": None,
    "active_run": None,
    "timeline": [],
    "upcoming_timeline": [],
    "upcoming_zone_timeline": [],
    "upcoming_zones": [],
    "updated_at": None,
}

DEFAULT_IRRIGATION_RUNTIME = {
    "status": "idle",
    "active_zone": None,
    "active_index": None,
    "duration_minutes": None,
    "zones": [],
    "started_at": None,
    "next_transition_at": None,
    "run_key": None,
    "last_event": None,
    "last_result": None,
}

DEFAULT_FAULT_STATUS = {
    "sprinkler_offline_count": 0,
    "thermostat_offline_count": 0,
    "stuck_valve_since": None,
    "manual_override": None,
    "last_fault_check": None,
}

DEFAULT_SPRINKLER = {
    "online": False,
    "node_online": False,
    "service_online": False,
    "backend_online": False,
    "running": False,
    "zone": None,
    "active_zone": None,
    "current_zone": None,
    "current_zone_index": None,
    "mode": "offline",
    "health": "offline",
    "heartbeat": "offline",
    "fault": True,
    "fault_code": "SPRINKLER_OFFLINE",
    "fault_message": "Sprinkler controller offline",
    "fault_severity": "critical",
    "alarms": [],
    "next_run": None,
    "next_zone": None,
    "remaining": None,
    "remaining_seconds": None,
    "zones": [],
    "relay_zones": [],
    "zone_count": SPRINKLER_ZONES,
    "program": None,
    "schedule": None,
    "timeline": [],
    "upcoming_timeline": [],
    "upcoming_zone_timeline": [],
    "upcoming_zones": [],
    "source": None,
    "error": None,
    "raw": None,
}

DEFAULT_THERMOSTAT = {
    "online": False,
    "node_online": False,
    "heartbeat": "offline",
    "source": None,
    "temp": None,
    "temperature": None,
    "current_temp": None,
    "humidity": None,
    "mode": "offline",
    "system_mode": "offline",
    "hvac_mode": "offline",
    "hvac_state": "OFFLINE",
    "health": "offline",
    "cooling": False,
    "heating": False,
    "fan": False,
    "fan_on": False,
    "cooling_active": False,
    "heating_active": False,
    "fan_active": False,
    "relay_cool": False,
    "relay_heat": False,
    "relay_fan": False,
    "relay_cool_stage1": False,
    "relay_cool_stage2": False,
    "relay_heat_stage1": False,
    "relay_heat_stage2": False,
    "cool_stage": 0,
    "heat_stage": 0,
    "cool_stage1": False,
    "cool_stage2": False,
    "heat_stage1": False,
    "heat_stage2": False,
    "setpoint": None,
    "fan_mode": None,
    "stage2_available": False,
    "stage2_enabled": False,
    "sensor_status": "unknown",
    "fault": True,
    "fault_code": "THERMOSTAT_OFFLINE",
    "fault_message": "Thermostat controller offline",
    "fault_severity": "critical",
    "alarms": [],
    "last_action": None,
    "error": None,
    "raw": None,
}

DEFAULT_WEATHER = {
    "online": False,
    "location": None,
    "temp": None,
    "feels_like": None,
    "humidity": None,
    "condition": "unknown",
    "rain_chance": None,
    "wind_mph": None,
    "precip_in": None,
    "forecast_today": None,
    "source": None,
    "updated_at": None,
    "cache_age_seconds": None,
    "error": None,
}

SNAPSHOT_REPLACE_KEYS = {
    "sprinkler",
    "thermostat",
    "weather",
}

PARTIAL_MERGE_KEYS = {
    "irrigation_schedule",
    "irrigation_runtime",
    "fault_status",
}

state = {
    "mode": "idle",
    "fault": None,
    "last_update": time.time(),

    "cpu": 0.0,
    "memory": 0.0,
    "gpu": 0.0,

    "ai_status": "idle",
    "last_decision": None,
    "last_execution": None,

    "automation_mode": "manual",
    "manual_override_until": 0.0,
    "manual_override_reason": None,
    "fault_status": deepcopy(DEFAULT_FAULT_STATUS),

    "sprinkler": deepcopy(DEFAULT_SPRINKLER),
    "thermostat": deepcopy(DEFAULT_THERMOSTAT),
    "weather": deepcopy(DEFAULT_WEATHER),

    "irrigation_schedule": deepcopy(DEFAULT_IRRIGATION_SCHEDULE),
    "irrigation_runtime": deepcopy(DEFAULT_IRRIGATION_RUNTIME),
}


def _device_fault_message(name: str, device: dict[str, Any]) -> str:
    if not isinstance(device, dict):
        return f"{name} unavailable"

    if device.get("fault_message"):
        return str(device.get("fault_message"))

    if device.get("error"):
        return str(device.get("error"))

    if device.get("health") == "offline":
        return f"{name} offline"

    if device.get("online") is False:
        return f"{name} offline"

    return ""


def _device_fault_active(device: dict[str, Any]) -> bool:
    if not isinstance(device, dict):
        return True

    if device.get("online") is False:
        return True

    if device.get("fault") is True:
        return True

    health = str(device.get("health") or "").lower()

    if health in {"offline", "fault", "error", "critical"}:
        return True

    return False


def _sync_global_fault_locked() -> None:
    current_fault = state.get("fault")

    if isinstance(current_fault, str) and current_fault.startswith("manual:"):
        state["mode"] = "fault"
        return

    thermostat = state.get("thermostat") or {}
    sprinkler = state.get("sprinkler") or {}

    if _device_fault_active(thermostat):
        message = _device_fault_message("thermostat", thermostat)
        state["fault"] = f"thermostat:{message or 'fault'}"
        state["mode"] = "fault"
        return

    if _device_fault_active(sprinkler):
        message = _device_fault_message("sprinkler", sprinkler)
        state["fault"] = f"sprinkler:{message or 'fault'}"
        state["mode"] = "fault"
        return

    state["fault"] = None

    if state.get("mode") == "fault":
        state["mode"] = "monitoring"


def update_state(**kwargs) -> None:
    with _state_lock:
        explicit_fault_update = "fault" in kwargs

        for key, value in kwargs.items():
            if key in SNAPSHOT_REPLACE_KEYS and isinstance(value, dict):
                state[key] = deepcopy(value)

            elif (
                key in PARTIAL_MERGE_KEYS
                and isinstance(value, dict)
                and isinstance(state.get(key), dict)
            ):
                merged = deepcopy(state[key])
                merged.update(deepcopy(value))
                state[key] = merged

            else:
                state[key] = deepcopy(value)

        state["last_update"] = time.time()

        if explicit_fault_update:
            if state.get("fault") is None:
                _sync_global_fault_locked()
            elif isinstance(state.get("fault"), str) and state["fault"].startswith("manual:"):
                state["mode"] = "fault"
        else:
            _sync_global_fault_locked()


def get_state_snapshot() -> dict[str, Any]:
    with _state_lock:
        return deepcopy(state)


def replace_device_state(name: str, value: dict[str, Any]) -> None:
    if name not in SNAPSHOT_REPLACE_KEYS:
        raise ValueError(f"Unknown device state: {name}")

    if not isinstance(value, dict):
        raise ValueError("Device state must be a dictionary")

    update_state(**{name: value})


def set_automation_mode(mode: str) -> dict[str, Any]:
    normalized = (mode or "").strip().lower()

    if normalized not in VALID_AUTOMATION_MODES:
        return {
            "ok": False,
            "error": "Invalid automation mode. Use 'manual' or 'auto'.",
            "allowed": sorted(VALID_AUTOMATION_MODES),
        }

    update_state(
        automation_mode=normalized,
        mode="monitoring",
        ai_status="active",
        last_decision={
            "action": "set_automation_mode",
            "reason": f"Automation mode changed to {normalized}",
            "result": {
                "ok": True,
                "automation_mode": normalized,
            },
            "source": "user",
            "requires_execution": False,
            "time": time.time(),
        },
    )

    return {
        "ok": True,
        "automation_mode": normalized,
        "mode": normalized,
    }


def set_manual_override_lock(
    reason: str,
    duration_seconds: float | int | None = None,
) -> dict[str, Any]:
    if duration_seconds is None:
        try:
            duration_seconds = float(os.getenv("ORION_MANUAL_OVERRIDE_SECONDS", "300"))
        except Exception:
            duration_seconds = 300

    duration = max(0.0, float(duration_seconds))
    until = time.time() + duration if duration > 0 else 0.0

    update_state(
        manual_override_until=until,
        manual_override_reason=reason or "Manual user control",
    )

    return {
        "ok": True,
        "manual_override_until": until,
        "manual_override_seconds": duration,
        "reason": reason or "Manual user control",
    }


def clear_manual_override_lock() -> dict[str, Any]:
    update_state(
        manual_override_until=0.0,
        manual_override_reason=None,
    )

    return {
        "ok": True,
        "manual_override_until": 0.0,
    }


def clear_fault() -> dict[str, Any]:
    with _state_lock:
        state["fault"] = None

        if state.get("mode") == "fault":
            state["mode"] = "monitoring"

        state["last_update"] = time.time()

    return {
        "ok": True,
        "fault": None,
    }