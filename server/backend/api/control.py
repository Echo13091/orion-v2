import time
from typing import Any

from flask import jsonify, request

from ai.brain import decide_background_action
from ai.router import execute_background_action
from core.event_store import record_event
from core.state import get_state_snapshot, set_automation_mode, update_state
from tools.device_control import (
    describe_control_capabilities,
    clear_skip_next_irrigation,
    get_irrigation_schedule,
    handle_device_command,
    run_sprinkler_program_now,
    run_sprinkler_zone,
    set_irrigation_schedule,
    set_thermostat_fan,
    set_thermostat_mode,
    set_thermostat_setpoint,
    skip_next_irrigation,
    stop_sprinkler,
)


VALID_AI_ACTIONS = {
    "observe",
    "delay_irrigation",
    "stop_sprinkler",
    "high_cpu",
    "high_memory",
    "handle_fault",
}


def _json_error(message: str, status: int = 400, **extra):
    payload = {
        "ok": False,
        "error": message,
    }
    payload.update(extra)
    return jsonify(payload), status


def _normalize_action(value: Any) -> str:
    action = str(value or "observe").strip().lower().replace(" ", "_").replace("-", "_")
    return action if action in VALID_AI_ACTIONS else "observe"


def _record_decision(
    *,
    action: str,
    reason: str,
    result: Any,
    source: str,
    params: dict[str, Any] | None = None,
    requires_execution: bool = False,
):
    update_state(
        ai_status="active",
        mode="monitoring",
        last_execution=result if isinstance(result, dict) and result.get("executed") else get_state_snapshot().get("last_execution"),
        last_decision={
            "action": action,
            "reason": reason,
            "params": params or {},
            "result": result,
            "source": source,
            "requires_execution": requires_execution,
            "time": time.time(),
        },
    )


def _record_manual_control(action: str, result, reason: str = "Manual user control"):
    update_state(
        ai_status="active",
        mode="monitoring",
        last_decision={
            "action": action,
            "reason": reason,
            "result": result,
            "source": "manual_control",
            "requires_execution": True,
            "time": time.time(),
        },
        last_execution=result if isinstance(result, dict) and result.get("ok") else get_state_snapshot().get("last_execution"),
    )



def _record_operations_manual_control_event(
    action: str,
    result,
    reason: str = "Manual user control",
    evidence_extra: dict[str, Any] | None = None,
):
    """
    Records manual commands into the Operations Console audit trail.
    Kept separate from _record_manual_control so existing Orion behavior stays intact.
    """
    try:
        payload = result if isinstance(result, dict) else {"result": result}

        evidence = {
            "action": action,
            "reason": reason,
            "result": payload,
        }

        if evidence_extra:
            evidence.update(evidence_extra)

        event_type = "manual_command"

        if action == "run_sprinkler_zone":
            event_type = "manual_zone_start"
        elif action == "stop_sprinkler":
            event_type = "manual_stop"
        elif action == "run_sprinkler_program":
            event_type = "manual_program_start"
        elif action == "skip_next_irrigation":
            event_type = "manual_skip"
        elif action == "clear_skip_next_irrigation":
            event_type = "manual_clear_skip"
        elif action == "set_irrigation_schedule":
            event_type = "manual_schedule_update"

        record_event(
            subsystem="irrigation",
            node="sprinkler-controller",
            severity="info",
            event_type=event_type,
            message=reason,
            source="manual_control",
            evidence=evidence,
        )
    except Exception as exc:
        print(f"[OPERATIONS] Failed to record manual control event: {exc}")

def _decision_from_request(data: dict[str, Any]) -> dict[str, Any]:
    action = _normalize_action(data.get("action"))
    params = data.get("params") if isinstance(data.get("params"), dict) else {}
    source = str(data.get("source") or "manual").strip().lower()

    # Pass source through params so router safety rules can distinguish a user
    # click from an autonomous background attempt.
    params = dict(params)
    params["source"] = source

    return {
        "action": action,
        "reason": str(data.get("reason") or f"User requested {action}"),
        "params": params,
        "source": source,
        "requires_execution": action in {"stop_sprinkler", "delay_irrigation"},
    }


_RECOMMENDATION_EVENT_CACHE: dict[str, float] = {}
_RECOMMENDATION_EVENT_THROTTLE_SECONDS = 300.0


def _record_operations_recommendation_event(decision: dict[str, Any]):
    """
    Records visible Decision Center / AI recommendation decisions into Operations.
    This keeps the Operations Console aligned with what the user actually sees.
    """
    try:
        action = str(decision.get("action") or "observe")
        source = str(decision.get("source") or "rules")
        reason = str(decision.get("reason") or "Automation recommendation generated")
        params = decision.get("params") if isinstance(decision.get("params"), dict) else {}
        requires_execution = bool(decision.get("requires_execution"))

        reason_lower = reason.lower()

        meaningful_policy_decision = (
            requires_execution
            or source in {"safety", "manual_override"}
            or "rain likely" in reason_lower
            or "irrigation" in reason_lower
            or "sprinkler" in reason_lower
            or "manual override" in reason_lower
        )

        if action == "observe" and source == "rules" and not meaningful_policy_decision:
            return

        key = f"{source}:{action}:{reason}:{params}"
        now_value = time.time()
        last_value = _RECOMMENDATION_EVENT_CACHE.get(key, 0.0)

        if now_value - last_value < _RECOMMENDATION_EVENT_THROTTLE_SECONDS:
            return

        _RECOMMENDATION_EVENT_CACHE[key] = now_value

        event_type = "automation_decision"

        if requires_execution:
            event_type = "automation_action_recommended"
        elif source == "manual_override":
            event_type = "automation_paused"
        elif source == "safety":
            event_type = "safety_decision"
        elif "rain" in reason_lower or "irrigation" in reason_lower or "sprinkler" in reason_lower:
            event_type = "automation_policy_decision"

        severity = "info"

        if source == "safety" or action in {"stop_sprinkler", "delay_irrigation", "skip_irrigation"}:
            severity = "warning"

        record_event(
            subsystem="automation",
            node="decision-center",
            severity=severity,
            event_type=event_type,
            message=reason,
            source=f"decision_center:{source}",
            evidence={
                "action": action,
                "source": source,
                "requires_execution": requires_execution,
                "params": params,
                "throttle_seconds": _RECOMMENDATION_EVENT_THROTTLE_SECONDS,
            },
        )
    except Exception as exc:
        print(f"[OPERATIONS] Failed to record recommendation event: {exc}")

def register_control(app):
    @app.route("/v1/control/help", methods=["GET"])
    def control_help():
        return jsonify(
            {
                "ok": True,
                "help": describe_control_capabilities(),
                "automation": {
                    "modes": ["manual", "auto"],
                    "default": "manual",
                    "current": get_state_snapshot().get("automation_mode"),
                    "note": "Auto mode allows bounded AI actions after safety checks.",
                },
            }
        )

    @app.route("/v1/control/command", methods=["POST"])
    def control_command():
        data = request.json or {}
        command = data.get("command", "")

        result = handle_device_command(command)
        _record_manual_control("device_control", result, f"Manual command: {command}")
        return jsonify(result)

    # -------------------------
    # AI AUTONOMY CONTROLS
    # -------------------------
    @app.route("/v1/control/ai/mode", methods=["GET", "POST"])
    def ai_mode():
        if request.method == "GET":
            state = get_state_snapshot()
            return jsonify(
                {
                    "ok": True,
                    "mode": state.get("automation_mode", "manual"),
                    "automation_mode": state.get("automation_mode", "manual"),
                }
            )

        data = request.json or {}
        mode = str(data.get("mode", "")).strip().lower()

        result = set_automation_mode(mode)

        if not result.get("ok"):
            return _json_error(result.get("error", "Invalid automation mode"), 400, result=result)

        return jsonify(result)

    @app.route("/v1/control/ai/recommendation", methods=["GET"])
    def ai_recommendation():
        decision = decide_background_action()
        state = get_state_snapshot()
        _record_operations_recommendation_event(decision)

        return jsonify(
            {
                "ok": True,
                "automation_mode": state.get("automation_mode"),
                "decision": decision,
            }
        )

    @app.route("/v1/control/ai/execute", methods=["POST"])
    def ai_execute():
        data = request.json or {}
        source = str(data.get("source") or "manual").strip().lower()

        if source not in {"manual", "auto"}:
            return _json_error("Invalid source. Use 'manual' or 'auto'.", 400)

        decision = _decision_from_request(data)
        state = get_state_snapshot()
        result = execute_background_action(
            decision,
            state,
            manual_override=(source == "manual"),
        )

        _record_decision(
            action=decision.get("action", "observe"),
            reason=decision.get("reason", "Manual AI action"),
            result=result,
            source=f"ui_{source}",
            params=decision.get("params", {}),
            requires_execution=decision.get("requires_execution", False),
        )

        return jsonify(
            {
                "ok": bool(result.get("ok")) if isinstance(result, dict) else True,
                "decision": decision,
                "result": result,
            }
        )

    @app.route("/v1/control/ai/apply", methods=["POST"])
    def ai_apply():
        # Manual UI approval. This bypasses automation_mode but still runs all
        # safety checks in execute_background_action().
        state = get_state_snapshot()
        decision = decide_background_action()
        result = execute_background_action(decision, state, manual_override=True)

        _record_decision(
            action=decision.get("action", "observe"),
            reason=decision.get("reason", "Manual apply recommendation"),
            result=result,
            source="manual_apply",
            params=decision.get("params", {}),
            requires_execution=decision.get("requires_execution", False),
        )

        return jsonify(
            {
                "ok": bool(result.get("ok")) if isinstance(result, dict) else True,
                "decision": decision,
                "result": result,
            }
        )

    # Backwards-friendly alias for frontend wording.
    @app.route("/v1/control/ai/apply-recommendation", methods=["POST"])
    def ai_apply_recommendation():
        return ai_apply()

    @app.route("/v1/control/sprinkler/zone", methods=["POST"])
    def sprinkler_zone():
        data = request.json or {}

        try:
            zone = int(data.get("zone", 0))
            minutes = int(data.get("minutes", 1))
        except Exception:
            return _json_error("Zone and minutes must be integers.")

        result = run_sprinkler_zone(zone=zone, minutes=minutes)
        _record_manual_control(
            "run_sprinkler_zone",
            result,
            f"Manual run zone {zone} for {minutes} minute(s)",
        )
        _record_operations_manual_control_event(
            "run_sprinkler_zone",
            result,
            f"Manual run zone {zone} for {minutes} minute(s)",
            {
                "zone": zone,
                "minutes": minutes,
                "command": "start_zone",
            },
        )
        return jsonify(result)

    @app.route("/v1/control/sprinkler/stop", methods=["POST"])
    def sprinkler_stop():
        result = stop_sprinkler()
        _record_manual_control("stop_sprinkler", result, "Manual sprinkler stop")
        _record_operations_manual_control_event(
            "stop_sprinkler",
            result,
            "Manual sprinkler stop",
            {
                "command": "stop",
            },
        )
        return jsonify(result)

    @app.route("/v1/control/sprinkler/program-now", methods=["POST"])
    def sprinkler_program_now():
        result = run_sprinkler_program_now()
        _record_manual_control("run_sprinkler_program", result, "Manual sprinkler program start")
        _record_operations_manual_control_event(
            "run_sprinkler_program",
            result,
            "Manual sprinkler program start",
            {
                "command": "program_now",
            },
        )
        return jsonify(result)

    @app.route("/v1/control/sprinkler/skip", methods=["POST"])
    def sprinkler_skip():
        data = request.json or {}
        reason = str(data.get("reason") or "Skipped by Orion recommendation")

        # This is the direct recommendation path. It calls the same device layer
        # that Orion chat uses, instead of only logging a recommendation. If the
        # sprinkler is actively running, skip_next_irrigation() also stops it.
        result = skip_next_irrigation(reason)

        if isinstance(result, dict) and isinstance(result.get("schedule"), dict):
            update_state(irrigation_schedule=result["schedule"])

        _record_manual_control(
            "skip_next_irrigation",
            result,
            reason,
        )
        _record_operations_manual_control_event(
            "skip_next_irrigation",
            result,
            reason,
            {
                "command": "skip_next",
            },
        )
        return jsonify(result)


    @app.route("/v1/control/sprinkler/clear-skip", methods=["POST"])
    def sprinkler_clear_skip():
        result = clear_skip_next_irrigation()

        if isinstance(result, dict) and isinstance(result.get("schedule"), dict):
            update_state(irrigation_schedule=result["schedule"])

        _record_manual_control(
            "clear_skip_next_irrigation",
            result,
            "Manual clear skip-next irrigation",
        )
        _record_operations_manual_control_event(
            "clear_skip_next_irrigation",
            result,
            "Manual clear skip-next irrigation",
            {
                "command": "clear_skip_next",
            },
        )
        return jsonify(result)

    @app.route("/v1/control/sprinkler/schedule", methods=["GET", "POST"])
    def sprinkler_schedule():
        if request.method == "GET":
            schedule = get_irrigation_schedule()
            update_state(irrigation_schedule=schedule)
            return jsonify(
                {
                    "ok": True,
                    "schedule": schedule,
                }
            )

        data = request.json or {}
        result = set_irrigation_schedule(
            enabled=data.get("enabled"),
            days=data.get("days"),
            start_time=data.get("start_time", data.get("time")),
            duration_minutes=data.get("duration_minutes", data.get("minutes")),
            zones=data.get("zones"),
            skip_if_rain_likely=data.get("skip_if_rain_likely"),
            sync_hardware=True,
        )

        if isinstance(result, dict) and isinstance(result.get("schedule"), dict):
            update_state(irrigation_schedule=result["schedule"])

        _record_manual_control(
            "set_irrigation_schedule",
            result,
            "Manual sprinkler schedule update",
        )
        _record_operations_manual_control_event(
            "set_irrigation_schedule",
            result,
            "Manual sprinkler schedule update",
            {
                "command": "schedule_update",
                "enabled": data.get("enabled"),
                "days": data.get("days"),
                "start_time": data.get("start_time", data.get("time")),
                "duration_minutes": data.get("duration_minutes", data.get("minutes")),
                "zones": data.get("zones"),
            },
        )
        return jsonify(result)

    @app.route("/v1/control/thermostat/setpoint", methods=["POST"])
    def thermostat_setpoint():
        data = request.json or {}

        try:
            temp = int(data.get("temp", data.get("setpoint", 0)))
        except Exception:
            return _json_error("Setpoint must be an integer.")

        result = set_thermostat_setpoint(temp)
        _record_manual_control("set_thermostat", result, f"Manual thermostat setpoint {temp}")
        return jsonify(result)

    @app.route("/v1/control/thermostat/mode", methods=["POST"])
    def thermostat_mode():
        data = request.json or {}
        mode = str(data.get("mode", ""))

        result = set_thermostat_mode(mode)
        _record_manual_control("set_thermostat_mode", result, f"Manual thermostat mode {mode}")
        return jsonify(result)

    @app.route("/v1/control/thermostat/fan", methods=["POST"])
    def thermostat_fan():
        data = request.json or {}
        mode = str(data.get("fan", data.get("mode", "")))

        result = set_thermostat_fan(mode)
        _record_manual_control("set_thermostat_fan", result, f"Manual thermostat fan {mode}")
        return jsonify(result)
