from flask import jsonify, request

from core.state import get_state_snapshot, update_state
from tools.environment import evaluate_environment


def register_system(app):
    @app.route("/v1/system", methods=["GET"])
    def system():
        state = get_state_snapshot()

        weather = state.get("weather") or {}
        sprinkler = state.get("sprinkler") or {}

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