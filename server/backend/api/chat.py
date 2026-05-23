from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from typing import Any

from flask import Response, jsonify, request

from ai.brain import decide_user_action
from ai.router import execute
from core.state import update_state
from memory.memory import add_message


RAW_CHAT_ACTIONS = {"get_system_status", "raw_system_status"}
STREAMING_ACTIONS = {"chat", "code"}


def _safe_text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def _format_bool(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if value is None:
        return "unknown"
    return str(value)


def _format_days(days: Any) -> str:
    if not isinstance(days, list) or not days:
        return "not set"

    weekday = ["mon", "tue", "wed", "thu", "fri"]
    weekend = ["sat", "sun"]

    lowered = [str(day).lower() for day in days]
    if lowered == weekday:
        return "weekdays"
    if lowered == weekend:
        return "weekends"
    if lowered == [*weekday, *weekend]:
        return "every day"

    return ", ".join(str(day).title() for day in days)


def _format_zones(zones: Any) -> str:
    if not isinstance(zones, list) or not zones:
        return "not set"

    try:
        nums = [int(z) for z in zones]
        if nums == list(range(min(nums), max(nums) + 1)):
            return f"{min(nums)}–{max(nums)}"
    except Exception:
        pass

    return ", ".join(str(z) for z in zones)


def _format_schedule_reply(value: dict[str, Any]) -> str:
    schedule = value.get("schedule") if isinstance(value.get("schedule"), dict) else {}
    days = _format_days(schedule.get("days"))
    start = _safe_text(schedule.get("start_time"), "not set")
    minutes = _safe_text(schedule.get("duration_minutes"), "not set")
    zones = _format_zones(schedule.get("zones"))
    enabled = bool(schedule.get("enabled", True))
    skip_next = bool(schedule.get("skip_next_run"))

    controller = schedule.get("controller") or value.get("controller") or "orion"
    controller_text = (
        "sprinkler controller synced"
        if controller == "sprinkler" or value.get("hardware_synced")
        else "Orion controlled"
    )

    lines = [
        "Irrigation schedule updated." if value.get("action") == "set_irrigation_schedule" else "Irrigation schedule updated in Orion.",
        f"• Status: {'enabled' if enabled else 'disabled'}",
        f"• Days: {days}",
        f"• Start: {start}",
        f"• Duration: {minutes} minute(s) per zone",
        f"• Zones: {zones}",
        f"• Controller: {controller_text}",
    ]

    if skip_next:
        lines.append("• Next run: skipped")

    return "\n".join(lines)


def _control_result_ok(value: dict[str, Any]) -> bool:
    if bool(value.get("ok")):
        return True

    result = value.get("result") if isinstance(value.get("result"), dict) else {}
    if bool(result.get("ok")):
        return True

    nested_result = result.get("result") if isinstance(result.get("result"), dict) else {}
    if bool(nested_result.get("ok")):
        return True

    if result.get("normalized_status") == "accepted_redirect":
        return True

    if nested_result.get("normalized_status") == "accepted_redirect":
        return True

    if result.get("controller_acknowledged") is True:
        return True

    if nested_result.get("controller_acknowledged") is True:
        return True

    return False


def _format_control_reply(value: dict[str, Any]) -> str:
    """Turn backend control JSON into a concise assistant message.

    The raw command result can contain endpoint attempts and device internals.
    That is useful for logs, but it is not useful as the primary chat reply.
    """
    ok = _control_result_ok(value)

    if ok:
        action = str(value.get("action") or "").strip()

        if action == "set_irrigation_schedule" or isinstance(value.get("schedule"), dict):
            return _format_schedule_reply(value)

        if action == "skip_next_irrigation":
            return "Next Orion-controlled irrigation run is marked skipped."

        if action == "clear_skip_next_irrigation":
            return "Next-run skip cleared. Orion will allow the next scheduled irrigation run."

        payload = value.get("payload") if isinstance(value.get("payload"), dict) else {}
        response = value.get("response") if isinstance(value.get("response"), dict) else {}

        setpoint = (
            payload.get("setpoint")
            or payload.get("temp")
            or response.get("setpoint")
            or response.get("temp")
        )
        if setpoint is not None and ("setpoint" in payload or "temp" in payload or "setpoint" in response):
            return f"Thermostat set to {setpoint}°F."

        if payload.get("mode") in {"auto", "cool", "heat", "off"}:
            return f"Thermostat mode set to {str(payload.get('mode')).title()}."

        fan_mode = payload.get("fan") or payload.get("mode") if ("fan" in payload) else None
        if fan_mode in {"auto", "on", "off"}:
            return f"Thermostat fan set to {str(fan_mode).title()}."

        if action.startswith("Zone ") or "zone" in value:
            return _safe_text(value.get("action"), "Sprinkler zone command completed.")

        message = (
            value.get("message")
            or value.get("status")
            or value.get("hardware_action")
            or action
        )

        if message:
            clean = _safe_text(message)
            if clean.lower() in {"ok", "success", "true"}:
                return "Command completed successfully."
            return clean if clean.endswith(".") else f"{clean}."

        return "Command completed successfully."

    error = _safe_text(value.get("error"), "Command failed.")

    if "No candidate endpoint accepted" in error:
        return (
            "Command failed because the device did not accept the actuator endpoint. "
            "Orion scheduling itself is local and does not require a hardware schedule API."
        )

    return f"Command failed: {error}"


def format_reply(value: Any, action: str | None = None) -> str:
    if isinstance(value, str):
        return value

    if isinstance(value, dict):
        # Only dump raw JSON when the user explicitly asks for raw/system JSON.
        if action in RAW_CHAT_ACTIONS:
            return json.dumps(value, indent=2, ensure_ascii=False, default=str)

        if "ok" in value or "error" in value or "hardware_synced" in value:
            return _format_control_reply(value)

        # Safety fallback: still avoid huge raw state dumps in normal chat.
        keys = set(value.keys())
        if {"weather", "sprinkler", "thermostat"}.issubset(keys):
            weather = value.get("weather") or {}
            sprinkler = value.get("sprinkler") or {}
            thermostat = value.get("thermostat") or {}
            return (
                "System snapshot: "
                f"weather={_safe_text(weather.get('condition'), 'unknown')}, "
                f"rain={_safe_text(weather.get('rain_chance'), 'unknown')}%, "
                f"sprinkler online={_format_bool(sprinkler.get('online'))}, "
                f"thermostat={_safe_text(thermostat.get('temp'), 'unknown')}°F. "
                "Ask for raw system JSON if you want the full dump."
            )

    try:
        return json.dumps(value, indent=2, ensure_ascii=False, default=str)
    except Exception:
        return str(value)


def sse_event(text: str) -> str:
    """Send streamed chunks as JSON strings so formatting survives."""
    return f"data: {json.dumps(str(text), ensure_ascii=False)}\n\n"


def _last_user_message(messages: list[Any]) -> str:
    for item in reversed(messages):
        if isinstance(item, dict) and item.get("role") == "user":
            return str(item.get("content", "")).strip()
    return ""


def register_chat(app):
    @app.route("/v1/chat/stream", methods=["POST"])
    def chat_stream():
        data = request.json or {}

        session_id = data.get("session_id") or str(uuid.uuid4())
        messages = data.get("messages", [])

        if not isinstance(messages, list) or not messages:
            return jsonify({"error": "No messages provided"}), 400

        user_message = _last_user_message(messages)
        if not user_message:
            return jsonify({"error": "No message content provided"}), 400

        add_message(session_id, "user", user_message)

        action = decide_user_action(user_message)
        update_state(ai_status="processing")

        def generate():
            full_reply = ""

            try:
                should_stream = action in STREAMING_ACTIONS

                try:
                    result = execute(action, user_message, stream=should_stream)
                except TypeError as exc:
                    # Compatibility with older router implementations.
                    if "stream" in str(exc):
                        result = execute(action, user_message)
                    else:
                        raise

                if isinstance(result, Iterator) and not isinstance(
                    result,
                    (str, bytes, dict, list, tuple),
                ):
                    for chunk in result:
                        chunk = str(chunk)
                        full_reply += chunk
                        yield sse_event(chunk)
                else:
                    full_reply = format_reply(result, action=action)
                    yield sse_event(full_reply)

            except GeneratorExit:
                raise

            except Exception as exc:  # noqa: BLE001
                error_text = f"ERROR: {exc}"
                full_reply += error_text
                yield sse_event(error_text)

            finally:
                if full_reply.strip():
                    add_message(session_id, "assistant", full_reply)

                # Chat should not overwrite last_decision. The decision panel is
                # owned by the background automation loop / manual Apply actions.
                update_state(ai_status="active")

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
                "X-Session-ID": session_id,
                "Access-Control-Expose-Headers": "X-Session-ID",
            },
        )
