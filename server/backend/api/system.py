from flask import jsonify, request

from core.state import get_state_snapshot, update_state


def register_system(app):
    @app.route("/v1/system", methods=["GET"])
    def system():
        return jsonify(get_state_snapshot())

    @app.route("/v1/system/fault", methods=["POST"])
    def set_fault():
        data = request.json or {}
        fault = (data.get("fault") or "").strip()

        if not fault:
            update_state(fault=None, mode="idle", ai_status="idle")
            return jsonify({"status": "cleared", "state": get_state_snapshot()})

        update_state(fault=f"manual:{fault}", mode="fault", ai_status="alert")
        return jsonify({"status": "set", "state": get_state_snapshot()})