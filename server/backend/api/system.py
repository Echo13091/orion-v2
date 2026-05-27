import os

import requests
from flask import jsonify, request

from core.event_store import record_state_transition
from core.state import get_state_snapshot, replace_device_state, update_state
from tools.environment import evaluate_environment


_LAST_IRRIGATION_RUNTIME_STATE = None

STANDALONE_IRRIGATION_BASE_URL = (
    os.getenv("ORION_STANDALONE_IRRIGATION_URL")
    or os.getenv("ORION_IRRIGATION_CONTROLLER_URL")
    or ""
).rstrip("/")


def _runtime_bool(value) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
            "running",
            "active",
        }

    return bool(value)


def _as_positive_zone(value):
    try:
        zone = int(value)
    except Exception:
        return None

    return zone if zone >= 1 else None


def _fetch_standalone_irrigation_status() -> dict | None:
    """Read the ESP32 standalone irrigation controller, when configured."""
    if not STANDALONE_IRRIGATION_BASE_URL:
        return None

    try:
        response = requests.get(
            f"{STANDALONE_IRRIGATION_BASE_URL}/api/status",
            headers={"Accept": "application/json"},
            timeout=2.5,
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else None
    except Exception as exc:
        return {
            "ok": False,
            "online": False,
            "error": str(exc),
            "source_url": STANDALONE_IRRIGATION_BASE_URL,
        }


def _normalize_standalone_irrigation(raw: dict) -> dict:
    rain = raw.get("rain_sensor") if isinstance(raw.get("rain_sensor"), dict) else {}
    schedule = raw.get("schedule") if isinstance(raw.get("schedule"), dict) else {}
    wifi = raw.get("wifi") if isinstance(raw.get("wifi"), dict) else {}

    online = bool(raw.get("ok", True)) and raw.get("online", True) is not False
    running = _runtime_bool(raw.get("running"))
    active_zone = _as_positive_zone(raw.get("active_zone"))
    rain_wet = bool(rain.get("wet"))
    schedule_status = schedule.get("status") or raw.get("schedule_status")
    fault_latched = bool(raw.get("fault_latched"))
    fault = bool(raw.get("fault")) or fault_latched

    if not online:
        health = "offline"
    elif fault:
        health = "fault"
    elif running:
        health = "running"
    elif rain_wet and rain.get("blocks_schedule"):
        health = "rain_inhibit"
    else:
        health = "online"

    fault_message = raw.get("fault_message") or raw.get("error")
    if rain_wet and rain.get("blocks_schedule") and not fault_message:
        fault_message = None

    return {
        "online": online,
        "node_online": online,
        "service_online": online,
        "backend_online": online,
        "controller_type": "standalone_esp32_irrigation",
        "display_name": "Standalone Irrigation Controller",
        "running": running,
        "active": running,
        "zone": active_zone,
        "active_zone": active_zone,
        "current_zone": active_zone,
        "mode": raw.get("mode") or ("manual" if running else "idle"),
        "status": "running" if running else "idle",
        "health": health,
        "heartbeat": "live",
        "fault": fault,
        "fault_code": "IRRIGATION_CONTROLLER_FAULT" if fault else None,
        "fault_message": fault_message,
        "fault_severity": "warning" if fault else None,
        "next_run": schedule_status,
        "remaining": raw.get("remaining_seconds"),
        "remaining_seconds": raw.get("remaining_seconds"),
        "program_active": raw.get("program_active"),
        "program_waiting": raw.get("program_waiting"),
        "rain_sensor": rain,
        "rain_inhibit": bool(rain_wet and rain.get("blocks_schedule")),
        "schedule_status": schedule_status,
        "schedule": schedule,
        "wifi": wifi,
        "time_valid": raw.get("time_valid"),
        "time_sync_source": raw.get("time_sync_source"),
        "zone_count": 8,
        "relay_zones": [],
        "source": "standalone_irrigation_controller",
        "source_url": STANDALONE_IRRIGATION_BASE_URL,
        "raw": raw,
    }


def _sprinkler_with_live_standalone(cached: dict) -> dict:
    raw = _fetch_standalone_irrigation_status()
    if raw is None:
        return cached

    if raw.get("ok") is False and raw.get("online") is False and "error" in raw:
        return {
            **cached,
            "online": False,
            "node_online": False,
            "service_online": False,
            "backend_online": False,
            "controller_type": "standalone_esp32_irrigation",
            "display_name": "Standalone Irrigation Controller",
            "running": False,
            "active": False,
            "health": "offline",
            "mode": "offline",
            "fault": True,
            "fault_code": "IRRIGATION_CONTROLLER_OFFLINE",
            "fault_message": raw.get("error") or "Standalone irrigation controller offline",
            "fault_severity": "warning",
            "source": "standalone_irrigation_controller",
            "source_url": STANDALONE_IRRIGATION_BASE_URL,
            "raw": raw,
        }

    return _normalize_standalone_irrigation(raw)


def _persist_live_sprinkler_state(sprinkler: dict) -> None:
    """Keep global fault logic aligned with the currently reachable controller."""
    try:
        if sprinkler.get("controller_type") == "standalone_esp32_irrigation":
            replace_device_state("sprinkler", sprinkler)
    except Exception as exc:
        print(f"[SYSTEM] Failed to persist live sprinkler state: {exc}")


def _sprinkler_runtime_state(sprinkler: dict) -> tuple[str, object]:
    running = (
        _runtime_bool(sprinkler.get("running"))
        or _runtime_bool(sprinkler.get("active"))
        or _runtime_bool(sprinkler.get("cycle_running"))
        or _runtime_bool(sprinkler.get("is_running"))
        or str(sprinkler.get("status") or "").strip().lower() == "running"
    )

    zone = sprinkler.get("zone") or sprinkler.get("active_zone")

    if running:
        return "manual_zone_running", zone

    return "idle", zone


def _record_irrigation_runtime_transition_if_changed(sprinkler: dict) -> None:
    global _LAST_IRRIGATION_RUNTIME_STATE

    try:
        current_state, zone = _sprinkler_runtime_state(sprinkler)

        if _LAST_IRRIGATION_RUNTIME_STATE is None:
            _LAST_IRRIGATION_RUNTIME_STATE = current_state
            return

        previous_state = _LAST_IRRIGATION_RUNTIME_STATE

        if previous_state == current_state:
            return

        _LAST_IRRIGATION_RUNTIME_STATE = current_state

        record_state_transition(
            subsystem="irrigation",
            node="standalone-irrigation-controller",
            from_state=previous_state,
            to_state=current_state,
            reason="Runtime irrigation controller state changed",
            source="runtime_state_monitor",
            evidence={
                "zone": zone,
                "sprinkler": sprinkler,
            },
        )
    except Exception as exc:
        print(f"[OPERATIONS] Failed to record irrigation runtime transition: {exc}")


def _compact_decision_state() -> dict:
    """
    Lightweight state for Decision Center.

    Avoids the full /v1/system payload and avoids recursive HTTP calls back
    into the backend while a sync Gunicorn worker is handling the request.
    """
    state = get_state_snapshot()

    weather = state.get("weather") or {}
    sprinkler = _sprinkler_with_live_standalone(state.get("sprinkler") or {})
    _persist_live_sprinkler_state(sprinkler)

    # Re-read after persistence so top-level fault/mode reflect the live controller.
    state = get_state_snapshot()
    thermostat = state.get("thermostat") or {}
    irrigation_schedule = state.get("irrigation_schedule") or {}
    irrigation_runtime = state.get("irrigation_runtime") or {}

    environment = evaluate_environment(
        grass_condition=None,
        weather=weather,
        sprinkler=sprinkler,
        rain_detection=sprinkler.get("rain_sensor"),
    )

    compact_sprinkler = {
        "online": sprinkler.get("online"),
        "running": sprinkler.get("running"),
        "active": sprinkler.get("active"),
        "zone": sprinkler.get("zone"),
        "active_zone": sprinkler.get("active_zone"),
        "mode": sprinkler.get("mode"),
        "status": sprinkler.get("status"),
        "health": sprinkler.get("health"),
        "heartbeat": sprinkler.get("heartbeat"),
        "fault": sprinkler.get("fault"),
        "fault_code": sprinkler.get("fault_code"),
        "fault_message": sprinkler.get("fault_message"),
        "next_run": sprinkler.get("next_run"),
        "next_zone": sprinkler.get("next_zone"),
        "remaining": sprinkler.get("remaining"),
        "remaining_seconds": sprinkler.get("remaining_seconds"),
        "relay_zones": sprinkler.get("relay_zones"),
        "zone_count": sprinkler.get("zone_count"),
        "controller_type": sprinkler.get("controller_type"),
        "display_name": sprinkler.get("display_name"),
        "rain_sensor": sprinkler.get("rain_sensor"),
        "rain_inhibit": sprinkler.get("rain_inhibit"),
        "schedule_status": sprinkler.get("schedule_status"),
        "time_valid": sprinkler.get("time_valid"),
        "time_sync_source": sprinkler.get("time_sync_source"),
        "source": sprinkler.get("source"),
        "source_url": sprinkler.get("source_url"),
        "raw": sprinkler.get("raw"),
    }

    compact_thermostat = {
        "online": thermostat.get("online"),
        "temperature": thermostat.get("temperature"),
        "temp": thermostat.get("temp"),
        "current_temp": thermostat.get("current_temp"),
        "humidity": thermostat.get("humidity"),
        "mode": thermostat.get("mode"),
        "hvac_mode": thermostat.get("hvac_mode"),
        "hvac_state": thermostat.get("hvac_state"),
        "health": thermostat.get("health"),
        "heartbeat": thermostat.get("heartbeat"),
        "cooling": thermostat.get("cooling"),
        "heating": thermostat.get("heating"),
        "fan": thermostat.get("fan"),
        "fan_mode": thermostat.get("fan_mode"),
        "setpoint": thermostat.get("setpoint"),
        "fault": thermostat.get("fault"),
        "fault_code": thermostat.get("fault_code"),
        "fault_message": thermostat.get("fault_message"),
    }

    compact_schedule = {
        "enabled": irrigation_schedule.get("enabled"),
        "start_time": irrigation_schedule.get("start_time"),
        "duration_minutes": irrigation_schedule.get("duration_minutes"),
        "zones": irrigation_schedule.get("zones"),
        "skip_next_run": irrigation_schedule.get("skip_next_run"),
        "skip_reason": irrigation_schedule.get("skip_reason"),
        "next_run": sprinkler.get("next_run"),
    }

    compact_runtime = {
        "status": irrigation_runtime.get("status"),
        "active_zone": irrigation_runtime.get("active_zone"),
        "duration_minutes": irrigation_runtime.get("duration_minutes"),
        "started_at": irrigation_runtime.get("started_at"),
        "next_transition_at": irrigation_runtime.get("next_transition_at"),
    }

    return {
        "ok": True,
        "mode": state.get("mode"),
        "ai_status": state.get("ai_status"),
        "automation_mode": state.get("automation_mode"),
        "fault": state.get("fault"),
        "cpu": state.get("cpu"),
        "memory": state.get("memory"),
        "gpu": state.get("gpu"),
        "last_update": state.get("last_update"),
        "last_decision": state.get("last_decision"),
        "last_execution": state.get("last_execution"),
        "manual_override_until": state.get("manual_override_until"),
        "manual_override_reason": state.get("manual_override_reason"),
        "fault_status": state.get("fault_status"),
        "weather": weather,
        "sprinkler": compact_sprinkler,
        "thermostat": compact_thermostat,
        "irrigation_runtime": compact_runtime,
        "irrigation_schedule": compact_schedule,
        "environment": environment,
    }


def register_system(app):
    @app.route("/v1/system/decision", methods=["GET"])
    def system_decision():
        return jsonify(_compact_decision_state())

    @app.route("/v1/system", methods=["GET"])
    def system():
        """
        Full system snapshot.

        Important: this route must not make HTTP calls back into this same
        backend process. Recursive self-HTTP can deadlock or stall a sync
        Gunicorn worker and make frontend pages appear unreliable.

        Vision-specific pages should call /v1/vision/* directly. The system
        snapshot can still include the latest cached/known state plus an
        environmental recommendation using trusted currently available inputs.
        """
        state = get_state_snapshot()

        weather = state.get("weather") or {}
        sprinkler = _sprinkler_with_live_standalone(state.get("sprinkler") or {})
        _persist_live_sprinkler_state(sprinkler)
        state = get_state_snapshot()
        state["sprinkler"] = sprinkler

        _record_irrigation_runtime_transition_if_changed(sprinkler)

        grass_condition = state.get("grass_condition")
        rain_detection = state.get("rain_detection") or sprinkler.get("rain_sensor")

        state["grass_condition"] = grass_condition
        state["rain_detection"] = rain_detection

        state["environment"] = evaluate_environment(
            grass_condition=grass_condition,
            weather=weather,
            sprinkler=sprinkler,
            rain_detection=rain_detection,
        )

        return jsonify(state)

    @app.route("/v1/system/fault", methods=["POST"])
    def set_fault():
        data = request.json or {}
        fault = (data.get("fault") or "").strip()

        if not fault:
            update_state(fault=None, mode="idle", ai_status="idle")
            return jsonify({"status": "cleared", "state": get_state_snapshot()})

        update_state(fault=f"manual:{fault}", mode="fault", ai_status="alert")
        return jsonify({"status": "set", "state": get_state_snapshot()})
