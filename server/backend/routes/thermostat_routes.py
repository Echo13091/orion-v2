from flask import Blueprint, jsonify, request

from thermostat_service import (
    get_thermostat,
    list_thermostats,
    recent_events,
    request_setpoint_change,
    update_thermostat,
)


thermostat_bp = Blueprint("thermostat", __name__)


@thermostat_bp.get("/v1/thermostats")
def thermostats_index():
    return jsonify(
        {
            "ok": True,
            "thermostats": list_thermostats(),
        }
    )


@thermostat_bp.get("/v1/thermostats/<thermostat_id>")
def thermostats_show(thermostat_id):
    thermostat = get_thermostat(thermostat_id)

    if not thermostat:
        return jsonify({"ok": False, "error": "thermostat_not_found"}), 404

    return jsonify(
        {
            "ok": True,
            "thermostat": thermostat,
        }
    )


@thermostat_bp.post("/v1/thermostats/ingest")
def thermostats_ingest():
    payload = request.get_json(silent=True) or {}
    thermostat = update_thermostat(payload)

    return jsonify(
        {
            "ok": True,
            "thermostat": thermostat,
        }
    )


@thermostat_bp.post("/v1/thermostats/<thermostat_id>/setpoint")
def thermostats_setpoint(thermostat_id):
    payload = request.get_json(silent=True) or {}

    try:
        setpoint = float(payload.get("setpoint"))
    except Exception:
        return jsonify({"ok": False, "error": "invalid_setpoint"}), 400

    try:
        result = request_setpoint_change(
            thermostat_id=thermostat_id,
            setpoint=setpoint,
            mode=payload.get("mode"),
            source=payload.get("source", "orion_dashboard"),
            reason=payload.get("reason", "Manual Orion setpoint request"),
        )
    except KeyError:
        return jsonify({"ok": False, "error": "thermostat_not_found"}), 404
    except ValueError as exc:
        return jsonify({"ok": False, "error": "setpoint_rejected", "message": str(exc)}), 400

    return jsonify(result)


@thermostat_bp.get("/v1/thermostats/events")
def thermostats_events():
    try:
        limit = int(request.args.get("limit", "25"))
    except Exception:
        limit = 25

    return jsonify(
        {
            "ok": True,
            "events": recent_events(limit=limit),
        }
    )
