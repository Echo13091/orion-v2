from flask import jsonify, request

from core.event_store import record_state_transition
from core.state import get_state_snapshot, update_state
from tools.environment import evaluate_environment


_LAST_IRRIGATION_RUNTIME_STATE = None


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
            node="sprinkler-controller",
            from_state=previous_state,
            to_state=current_state,
            reason="Runtime sprinkler state changed",
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
    sprinkler = state.get("sprinkler") or {}
    thermostat = state.get("thermostat") or {}
    irrigation_schedule = state.get("irrigation_schedule") or {}
    irrigation_runtime = state.get("irrigation_runtime") or {}

    environment = evaluate_environment(
        grass_condition=None,
        weather=weather,
        sprinkler=sprinkler,
        rain_detection=None,
    )

    compact_sprinkler = {
        "online": sprinkler.get("online"),
        "running": sprinkler.get("running"),
        "active": sprinkler.get("active"),
        "zone": sprinkler.get("zone"),
        "active_zone": sprinkler.get("active_zone"),
        "mode": sprinkler.get("mode"),
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
        sprinkler = state.get("sprinkler") or {}

        _record_irrigation_runtime_transition_if_changed(sprinkler)

        grass_condition = state.get("grass_condition")
        rain_detection = state.get("rain_detection")

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