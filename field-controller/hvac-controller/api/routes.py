from flask import Blueprint, jsonify, render_template, request

from core.state import (
    clear_reported_fault,
    get_public_state,
    set_fan_mode,
    set_mode,
    set_reported_fault,
    set_setpoint,
)

hvac_bp = Blueprint("hvac", __name__)


def _payload():
    return request.get_json(silent=True) or request.form or {}


def _bool_ok(data, status=200):
    return jsonify(data), status


def _as_false(value):
    if value is False:
        return True
    return str(value or "").strip().lower() in {
        "0",
        "false",
        "off",
        "clear",
        "cleared",
        "resolve",
        "resolved",
        "reset",
        "none",
        "normal",
        "ok",
    }


@hvac_bp.route("/")
def index():
    return render_template("index.html")


# -------------------------
# STATUS ALIASES
# -------------------------
@hvac_bp.route("/api/hvac/status")
@hvac_bp.route("/api/status")
@hvac_bp.route("/status")
@hvac_bp.route("/api/thermostat/status")
def status():
    return jsonify(get_public_state())


# -------------------------
# SETPOINT ALIASES
# -------------------------
@hvac_bp.route("/api/hvac/setpoint", methods=["POST"])
@hvac_bp.route("/api/hvac/set_temp", methods=["POST"])
@hvac_bp.route("/api/hvac/temp", methods=["POST"])
@hvac_bp.route("/api/setpoint", methods=["POST"])
@hvac_bp.route("/api/set_temp", methods=["POST"])
@hvac_bp.route("/setpoint", methods=["POST"])
def setpoint():
    data = _payload()

    try:
        raw = (
            data.get("setpoint")
            or data.get("temp")
            or data.get("temperature")
            or data.get("value")
        )
        if raw is None or raw == "":
            return _bool_ok({"ok": False, "error": "empty setpoint"}, 400)

        sp = int(float(raw))
        set_setpoint(sp)
        return jsonify({"ok": True, "setpoint": sp, "action": "setpoint"})
    except ValueError as exc:
        return _bool_ok({"ok": False, "error": str(exc)}, 400)
    except Exception as exc:
        print("SETPOINT ERROR:", exc)
        return _bool_ok({"ok": False, "error": "invalid input"}, 400)


# -------------------------
# HVAC MODE ALIASES
# -------------------------
@hvac_bp.route("/api/hvac/mode", methods=["POST"])
@hvac_bp.route("/api/mode", methods=["POST"])
@hvac_bp.route("/mode", methods=["POST"])
def mode():
    data = _payload()
    mode_value = str(data.get("mode", data.get("hvac_mode", ""))).lower().strip()

    try:
        set_mode(mode_value)
        return jsonify({"ok": True, "mode": mode_value, "action": "mode"})
    except ValueError as exc:
        return _bool_ok({"ok": False, "error": str(exc)}, 400)


# -------------------------
# FAN MODE ALIASES
# -------------------------
@hvac_bp.route("/api/hvac/fan", methods=["POST"])
@hvac_bp.route("/api/fan", methods=["POST"])
@hvac_bp.route("/fan", methods=["POST"])
def fan():
    data = _payload()
    fan_value = str(
        data.get("fan", data.get("mode", data.get("fan_mode", "")))
    ).lower().strip()

    try:
        set_fan_mode(fan_value)
        return jsonify({"ok": True, "fan": fan_value, "fan_mode": fan_value, "action": "fan"})
    except ValueError as exc:
        return _bool_ok({"ok": False, "error": str(exc)}, 400)


# -------------------------
# FAULT REPORTING / CLEARING
# -------------------------
@hvac_bp.route("/api/hvac/fault", methods=["POST"])
@hvac_bp.route("/api/fault", methods=["POST"])
@hvac_bp.route("/fault", methods=["POST"])
def fault():
    data = _payload()
    action = str(data.get("action", "")).lower().strip()
    code = data.get("code") or data.get("fault_code") or data.get("fault")

    should_clear = action in {"clear", "resolve", "resolved", "reset"} or _as_false(
        data.get("active", data.get("fault_active", ""))
    )

    if should_clear:
        clear_reported_fault(code if code else None)
        return jsonify({"ok": True, "action": "fault_clear", "code": code or "all"})

    if not code:
        return _bool_ok({"ok": False, "error": "missing fault code"}, 400)

    message = data.get("message") or data.get("fault_message") or code
    severity = data.get("severity") or data.get("fault_severity") or "warning"
    source = data.get("source") or data.get("fault_source") or "api"

    set_reported_fault(code, message, severity=severity, source=source, active=True)
    return jsonify(
        {
            "ok": True,
            "action": "fault_set",
            "code": str(code).upper(),
            "message": message,
            "severity": severity,
            "source": source,
        }
    )


@hvac_bp.route("/api/hvac/fault", methods=["DELETE"])
@hvac_bp.route("/api/fault", methods=["DELETE"])
def clear_faults():
    code = request.args.get("code") or request.args.get("fault_code")
    clear_reported_fault(code if code else None)
    return jsonify({"ok": True, "action": "fault_clear", "code": code or "all"})


@hvac_bp.route("/api/hvac/capabilities")
@hvac_bp.route("/api/capabilities")
def capabilities():
    return jsonify(
        {
            "ok": True,
            "service": "hvac",
            "endpoints": {
                "status": [
                    "/api/hvac/status",
                    "/api/status",
                    "/status",
                    "/api/thermostat/status",
                ],
                "setpoint": [
                    "/api/hvac/setpoint",
                    "/api/hvac/set_temp",
                    "/api/hvac/temp",
                    "/api/setpoint",
                    "/api/set_temp",
                    "/setpoint",
                ],
                "mode": ["/api/hvac/mode", "/api/mode", "/mode"],
                "fan": ["/api/hvac/fan", "/api/fan", "/fan"],
                "fault": ["/api/hvac/fault", "/api/fault", "/fault"],
            },
            "modes": ["off", "cool", "heat", "auto"],
            "fan_modes": ["auto", "on", "off"],
            "health_states": ["online", "fault", "offline"],
            "fault_fields": [
                "fault",
                "fault_code",
                "fault_message",
                "fault_severity",
                "faults",
                "alarms",
                "health",
                "status",
            ],
        }
    )
