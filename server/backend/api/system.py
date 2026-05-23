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


def register_system(app):
    @app.route("/v1/system", methods=["GET"])
    def system():
        state = get_state_snapshot()

        weather = state.get("weather") or {}
        sprinkler = state.get("sprinkler") or {}
        _record_irrigation_runtime_transition_if_changed(sprinkler)

        grass_condition = None
        rain_detection = None

        try:
            import json
            import urllib.request

            with urllib.request.urlopen(
                "http://localhost:5001/v1/vision/grass-condition",
                timeout=2,
            ) as response:
                grass_condition = json.loads(
                    response.read().decode("utf-8")
                )

        except Exception:
            grass_condition = None

        try:
            import json
            import urllib.request

            with urllib.request.urlopen(
                "http://localhost:5001/v1/vision/rain-detection",
                timeout=2,
            ) as response:
                rain_detection = json.loads(
                    response.read().decode("utf-8")
                )

        except Exception:
            rain_detection = None

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