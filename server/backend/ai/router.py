from __future__ import annotations

import json
import os
import time
from typing import Any, Callable

from tools.backtest import run_backtest
from tools.system_tools import get_system_status
from tools.device_control import describe_control_capabilities, describe_irrigation_schedule, handle_device_command, stop_sprinkler

try:
    from tools.device_control import skip_next_irrigation as _real_skip_next_irrigation
except Exception:  # Compatibility if the schedule patch is not installed yet.
    _real_skip_next_irrigation = None

from core.state import get_state_snapshot, update_state
from ai.llm import run_llm, stream_llm


EXECUTABLE_BACKGROUND_ACTIONS = {
    "delay_irrigation",
    "skip_irrigation",
    "stop_sprinkler",
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "running", "active"}
    return bool(value)


def _sprinkler_running(sprinkler: dict[str, Any]) -> bool:
    if _safe_bool(sprinkler.get("running")):
        return True
    if _safe_bool(sprinkler.get("active")):
        return True
    if _safe_bool(sprinkler.get("cycle_running")):
        return True
    if _safe_bool(sprinkler.get("is_running")):
        return True

    zones = sprinkler.get("zones") or sprinkler.get("zone_states")
    if isinstance(zones, list) and any(_safe_bool(item) for item in zones):
        return True

    raw = sprinkler.get("raw")
    if isinstance(raw, dict):
        return _sprinkler_running(raw)

    return False


def _compact_state_for_prompt() -> dict[str, Any]:
    state = get_state_snapshot()

    weather = state.get("weather") or {}
    sprinkler = state.get("sprinkler") or {}
    thermostat = state.get("thermostat") or {}

    return {
        "mode": state.get("mode"),
        "automation_mode": state.get("automation_mode"),
        "fault": state.get("fault"),
        "cpu": state.get("cpu"),
        "memory": state.get("memory"),
        "gpu": state.get("gpu"),
        "ai_status": state.get("ai_status"),
        "last_decision": state.get("last_decision"),
        "last_execution": state.get("last_execution"),
        "irrigation_schedule": state.get("irrigation_schedule"),
        "weather": {
            "online": weather.get("online"),
            "location": weather.get("location"),
            "temp": weather.get("temp"),
            "feels_like": weather.get("feels_like"),
            "humidity": weather.get("humidity"),
            "condition": weather.get("condition"),
            "rain_chance": weather.get("rain_chance"),
            "wind_mph": weather.get("wind_mph"),
            "precip_in": weather.get("precip_in"),
        },
        "sprinkler": {
            "online": sprinkler.get("online"),
            "running": _sprinkler_running(sprinkler),
            "zone": sprinkler.get("zone") or sprinkler.get("active_zone"),
            "mode": sprinkler.get("mode"),
            "next_run": sprinkler.get("next_run"),
        },
        "thermostat": {
            "online": thermostat.get("online"),
            "temp": thermostat.get("temp"),
            "humidity": thermostat.get("humidity"),
            "mode": thermostat.get("mode"),
            "cooling": thermostat.get("cooling"),
            "heating": thermostat.get("heating"),
            "fan": thermostat.get("fan"),
        },
    }


def build_orion_chat_prompt(prompt: str | None) -> str:
    user_prompt = (prompt or "").strip()
    state = _compact_state_for_prompt()

    return f"""
You are Orion, a home automation assistant.
You are NOT NASA Orion. Do not talk about spacecraft, Artemis, NASA missions, or unrelated Orion topics unless the user explicitly asks for them.

Your job:
- Explain the live home system state.
- Explain weather, irrigation, thermostat, and system-health decisions.
- Be concise and practical.
- Never invent sensor values. Use only the current state below.
- If the user asks for device action details, explain the safe command path.
- If current data is missing, say it is missing.

Current Orion home state JSON:
{json.dumps(state, indent=2, default=str)}

User asked:
{user_prompt}
""".strip()



# -------------------------
# CHAT / SUMMARY HELPERS
# -------------------------
def _fmt_temp(value: Any) -> str:
    try:
        if value is None:
            return "unknown"
        return f"{float(value):.1f}°F"
    except Exception:
        return "unknown"


def _fmt_percent(value: Any, decimals: int = 0) -> str:
    try:
        if value is None:
            return "unknown"
        return f"{float(value):.{decimals}f}%"
    except Exception:
        return "unknown"


def _fmt_number(value: Any, suffix: str = "") -> str:
    try:
        if value is None:
            return "unknown"
        return f"{float(value):.1f}{suffix}"
    except Exception:
        return "unknown"


def _fmt_bool(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if value is None:
        return "unknown"
    return str(value)


def _title_action(action: Any) -> str:
    text = str(action or "monitoring").replace("_", " ").replace("-", " ").strip()
    return text.title() if text else "Monitoring"


def _schedule_summary(schedule: dict[str, Any]) -> str:
    if not isinstance(schedule, dict) or not schedule:
        return "No irrigation schedule is loaded."

    try:
        base = describe_irrigation_schedule(schedule)
    except Exception:
        enabled = "enabled" if schedule.get("enabled") else "disabled"
        days = schedule.get("days") or []
        day_text = ", ".join(str(day) for day in days) if days else "no days set"
        start_time = schedule.get("start_time") or "no start time"
        minutes = schedule.get("duration_minutes") or schedule.get("minutes") or "unknown"
        zones = schedule.get("zones") or []
        zone_text = ", ".join(str(z) for z in zones) if zones else "no zones set"
        base = f"Irrigation schedule is {enabled}: {day_text} at {start_time}, {minutes} minute(s), zones {zone_text}. Orion owns scheduling."

    event = schedule.get("last_scheduler_event")
    if isinstance(event, dict) and event.get("message"):
        return base + f" Last scheduler event: {event.get('message')}"

    return base


def summarize_weather_state(prompt: str | None = None) -> str:
    state = _compact_state_for_prompt()
    weather = state.get("weather") or {}
    sprinkler = state.get("sprinkler") or {}
    schedule = state.get("irrigation_schedule") or {}

    if not weather.get("online"):
        error = weather.get("error") or "weather data is unavailable"
        return f"Weather is currently offline: {error}. Orion will avoid weather-based assumptions until data returns."

    rain = _safe_float(weather.get("rain_chance"))
    location = weather.get("location") or "current location"
    condition = weather.get("condition") or "unknown"

    lines = [
        f"Current weather for {location}: {condition}, {_fmt_temp(weather.get('temp'))}, feels like {_fmt_temp(weather.get('feels_like'))}.",
        f"Humidity is {_fmt_percent(weather.get('humidity'))}, wind is {_fmt_number(weather.get('wind_mph'), ' mph')}, and rain chance is {_fmt_percent(rain)}.",
    ]

    if rain >= 70:
        if _sprinkler_running(sprinkler):
            lines.append("Impact: rain is likely while irrigation is active, so Orion recommends stopping the sprinkler.")
        else:
            lines.append("Impact: rain is likely, so Orion recommends skipping or delaying the next irrigation run.")
    elif rain >= 40:
        lines.append("Impact: rain is possible, so Orion should keep monitoring before watering.")
    else:
        lines.append("Impact: rain risk is low, so weather is not currently blocking irrigation.")

    if isinstance(schedule, dict) and schedule.get("skip_next_run"):
        lines.append("Current irrigation state: the next run is already marked skipped.")

    return "\n".join(lines)


def summarize_system_state(prompt: str | None = None) -> str:
    state = _compact_state_for_prompt()
    fault = state.get("fault")
    decision = state.get("last_decision") or {}
    execution = state.get("last_execution") or {}

    health = "healthy" if not fault else f"faulted: {fault}"
    lines = [
        f"System is {health}.",
        f"Automation mode is {state.get('automation_mode') or 'manual'} and AI status is {state.get('ai_status') or 'unknown'}.",
        f"Load: CPU {_fmt_percent(state.get('cpu'), 1)}, memory {_fmt_percent(state.get('memory'), 1)}, GPU {_fmt_percent(state.get('gpu'), 1)}.",
    ]

    if decision:
        lines.append(
            f"Last decision: {_title_action(decision.get('action'))} — {decision.get('reason') or 'no reason recorded'}."
        )

    if execution:
        if execution.get("executed"):
            lines.append(f"Last execution: {_title_action(execution.get('action'))} succeeded.")
        elif execution.get("blocked"):
            lines.append(f"Last execution was blocked: {execution.get('reason') or 'no reason recorded'}.")

    return "\n".join(lines)


def summarize_sprinkler_state(prompt: str | None = None) -> str:
    state = _compact_state_for_prompt()
    sprinkler = state.get("sprinkler") or {}
    schedule = state.get("irrigation_schedule") or {}

    if not sprinkler.get("online"):
        return "Sprinkler is offline. Orion cannot safely run irrigation commands until it comes back online."

    running = _sprinkler_running(sprinkler)
    zone = sprinkler.get("zone") or "no active zone"
    mode = sprinkler.get("mode") or "unknown"

    lines = [
        f"Sprinkler is online and currently {'running' if running else 'not running'}.",
        f"Mode is {mode}; active zone is {zone}.",
        _schedule_summary(schedule),
    ]

    return "\n".join(lines)


def summarize_thermostat_state(prompt: str | None = None) -> str:
    state = _compact_state_for_prompt()
    thermostat = state.get("thermostat") or {}

    if not thermostat.get("online"):
        return "Thermostat is offline. Orion cannot safely change HVAC settings until it comes back online."

    active = []
    if thermostat.get("cooling"):
        active.append("cooling")
    if thermostat.get("heating"):
        active.append("heating")
    if thermostat.get("fan"):
        active.append("fan")

    active_text = ", ".join(active) if active else "idle"

    return "\n".join([
        f"Thermostat is online at {_fmt_temp(thermostat.get('temp'))} with {_fmt_percent(thermostat.get('humidity'))} humidity.",
        f"HVAC mode is {thermostat.get('mode') or 'unknown'} and current equipment state is {active_text}.",
    ])


def summarize_recommendation_state(prompt: str | None = None) -> str:
    state = _compact_state_for_prompt()
    weather = state.get("weather") or {}
    sprinkler = state.get("sprinkler") or {}
    schedule = state.get("irrigation_schedule") or {}
    decision = state.get("last_decision") or {}
    execution = state.get("last_execution") or {}

    rain = _safe_float(weather.get("rain_chance"))
    running = _sprinkler_running(sprinkler)

    lines = []
    if rain >= 70:
        if running:
            lines.append(f"Orion recommends stopping irrigation because rain chance is {_fmt_percent(rain)} and the sprinkler is running.")
        else:
            lines.append(f"Orion recommends delaying irrigation because rain chance is {_fmt_percent(rain)} and the sprinkler is not currently running.")
    else:
        lines.append(f"Orion is monitoring. Rain chance is {_fmt_percent(rain)}, so irrigation is not being blocked by weather right now.")

    if decision:
        lines.append(f"Current decision: {_title_action(decision.get('action'))} — {decision.get('reason') or 'no reason recorded'}.")

    if isinstance(schedule, dict) and schedule.get("skip_next_run"):
        lines.append("The next irrigation run is already marked skipped in Orion.")

    if isinstance(schedule, dict):
        lines.append("Schedule control: Orion coordinates the schedule and syncs it to the sprinkler controller when available.")

    if execution:
        if execution.get("executed"):
            lines.append(f"Last hardware execution succeeded: {_title_action(execution.get('action'))}.")
        elif execution.get("blocked"):
            lines.append(f"Last hardware execution was blocked: {execution.get('reason') or 'no reason recorded'}.")

    return "\n".join(lines)


def _automation_mode(state: dict[str, Any]) -> str:
    mode = str(state.get("automation_mode") or "manual").strip().lower()
    return mode if mode in {"manual", "auto"} else "manual"


def _blocked(reason: str, *, action: str, decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "executed": False,
        "blocked": True,
        "action": action,
        "reason": reason,
        "decision": decision,
        "time": time.time(),
    }


def _no_hardware_needed(action: str, decision: dict[str, Any], message: str) -> dict[str, Any]:
    return {
        "ok": True,
        "executed": False,
        "blocked": False,
        "action": action,
        "message": message,
        "decision": decision,
        "time": time.time(),
    }


def _skip_next_irrigation(reason: str) -> dict[str, Any]:
    """Use the real schedule function if installed; otherwise mark local state."""
    if callable(_real_skip_next_irrigation):
        return _real_skip_next_irrigation(reason)

    now = time.time()
    update_state(
        sprinkler={"next_run": "Next run skipped"},
        irrigation_schedule={
            "skip_next_run": True,
            "skip_reason": reason,
            "updated_at": now,
            "hardware_synced": True,
            "hardware_result": {
                "ok": True,
                "message": "No hardware schedule sync required. Orion controls scheduled runs directly.",
            },
        },
    )

    return {
        "ok": True,
        "controller": "orion",
        "hardware_synced": True,
        "message": "Next irrigation run marked skipped in Orion schedule.",
        "reason": reason,
        "time": now,
    }


def is_safe_to_execute(
    action: str,
    state: dict[str, Any],
    params: dict[str, Any] | None = None,
    *,
    decision_source: str | None = None,
) -> tuple[bool, str]:
    params = params or {}

    if state.get("fault"):
        return False, f"System fault present: {state.get('fault')}"

    normalized = (action or "").strip().lower()
    if normalized == "skip_irrigation":
        normalized = "delay_irrigation"

    sprinkler = state.get("sprinkler") or {}
    weather = state.get("weather") or {}
    source = str(params.get("source") or decision_source or "").strip().lower()

    if normalized == "delay_irrigation":
        rain_chance = _safe_float(weather.get("rain_chance"))

        if rain_chance >= 70 or source in {"manual", "user", "rules"}:
            return True, "Safe to delay irrigation"

        return False, "No rain/safety reason to delay irrigation"

    if normalized == "stop_sprinkler":
        if sprinkler.get("online") is False:
            return False, "Sprinkler is offline"

        if not _sprinkler_running(sprinkler):
            return False, "Sprinkler is not running"

        rain_chance = _safe_float(weather.get("rain_chance"))

        # Emergency/user/rules stops are allowed. Autonomous stops require
        # evidence such as rain or a rules source.
        if rain_chance >= 70 or source in {"manual", "user", "rules"}:
            return True, "Safe to stop sprinkler"

        return False, "No rain/safety reason to stop sprinkler"

    return False, f"Action '{action}' is not executable"


def execute_background_action(
    decision: dict[str, Any],
    state: dict[str, Any] | None = None,
    *,
    manual_override: bool = False,
) -> dict[str, Any]:
    """Execute a bounded AI background action.

    manual_override=True is used by the UI's Apply Recommendation button.
    Auto execution only happens when state.automation_mode == 'auto'.
    """
    current_state = state or get_state_snapshot()
    action = str(decision.get("action") or "observe").strip().lower()
    if action == "skip_irrigation":
        action = "delay_irrigation"

    params = decision.get("params") if isinstance(decision.get("params"), dict) else {}
    source = str(decision.get("source") or "").strip().lower()

    sprinkler = current_state.get("sprinkler") or {}
    schedule = current_state.get("irrigation_schedule") or {}

    if action == "delay_irrigation" and bool(schedule.get("skip_next_run")):
        return _no_hardware_needed(
            action,
            decision,
            "Next irrigation run is already marked skipped.",
        )

    if action == "stop_sprinkler" and not _sprinkler_running(sprinkler):
        return _no_hardware_needed(
            action,
            decision,
            "Sprinkler is already stopped.",
        )

    if action == "observe":
        return _no_hardware_needed(action, decision, "Monitoring system")

    if action in {"high_cpu", "high_memory", "handle_fault"}:
        return _no_hardware_needed(action, decision, "System event logged")

    if action not in EXECUTABLE_BACKGROUND_ACTIONS:
        return _blocked("Action is not in executable allow-list", action=action, decision=decision)

    manual_until = _safe_float(current_state.get("manual_override_until"), 0.0)
    if manual_until and manual_until > time.time() and not manual_override:
        return _blocked(
            f"Manual override lock active. Wait {max(0, manual_until - time.time()):.0f}s.",
            action=action,
            decision=decision,
        )

    if _automation_mode(current_state) != "auto" and not manual_override:
        return _blocked(
            "Automation mode is manual. Waiting for user approval.",
            action=action,
            decision=decision,
        )

    safe, reason = is_safe_to_execute(
        action,
        current_state,
        params,
        decision_source=source,
    )
    if not safe:
        return _blocked(reason, action=action, decision=decision)

    if action == "delay_irrigation":
        result = _skip_next_irrigation(decision.get("reason") or "Delayed by Orion")
        return {
            "ok": bool(result.get("ok")),
            "executed": bool(result.get("ok")),
            "blocked": False,
            "action": action,
            "hardware_action": "sprinkler.skip_next_irrigation",
            "safety_reason": reason,
            "result": result,
            "decision": decision,
            "time": time.time(),
        }

    if action == "stop_sprinkler":
        result = stop_sprinkler()
        return {
            "ok": bool(result.get("ok")),
            "executed": bool(result.get("ok")),
            "blocked": False,
            "action": action,
            "hardware_action": "sprinkler.stop",
            "safety_reason": reason,
            "result": result,
            "decision": decision,
            "time": time.time(),
        }

    return _blocked("No executor implemented for action", action=action, decision=decision)


def execute(action: str, prompt: str | None = None, stream: bool = False):
    # -------------------------
    # SYSTEM ACTIONS
    # -------------------------
    if action == "run_backtest":
        return run_backtest(prompt)

    # Raw JSON only. Normal user-facing status requests should use summaries.
    if action in {"get_system_status", "raw_system_status"}:
        return get_system_status()

    if action == "system_summary":
        return summarize_system_state(prompt)

    if action == "weather_summary":
        return summarize_weather_state(prompt)

    if action == "sprinkler_summary":
        return summarize_sprinkler_state(prompt)

    if action == "thermostat_summary":
        return summarize_thermostat_state(prompt)

    if action == "recommendation_summary":
        return summarize_recommendation_state(prompt)

    if action == "observe":
        return "Monitoring system"

    if action == "high_cpu":
        return "⚠️ CPU spike detected"

    if action == "high_memory":
        return "⚠️ Memory spike detected"

    if action == "handle_fault":
        return "⚠️ Handling fault"

    # -------------------------
    # DEVICE CONTROL
    # -------------------------
    if action == "control_help":
        return describe_control_capabilities()

    if action == "device_control":
        return handle_device_command(prompt)

    # -------------------------
    # CHAT
    # -------------------------
    if action == "chat":
        lower = (prompt or "").lower()

        if "mistral or deepseek" in lower or "what model" in lower or "models" in lower:
            edge = os.getenv("ORION_EDGE_MODE", "1").strip().lower() in {"1", "true", "yes", "on"}
            default_model = os.getenv("ORION_MODEL_DEFAULT", "tinyllama:1.1b")
            code_model = os.getenv("ORION_MODEL_CODE", "deepseek-coder:6.7b")
            return (
                "Orion is optimized for edge mode. Background decisions and common home-state explanations use fast rules, not an LLM. "
                f"Optional free-form chat model: {default_model}. Optional code model: {code_model}. "
                f"Edge mode is {'on' if edge else 'off'}."
            )

        grounded_prompt = build_orion_chat_prompt(prompt)

        if stream:
            return stream_llm(grounded_prompt, mode="default")

        return run_llm(grounded_prompt, mode="default")

    # -------------------------
    # CODE
    # -------------------------
    if action == "code":
        if stream:
            return stream_llm(prompt or "", mode="code")

        return run_llm(prompt or "", mode="code")

    return f"Unknown action: {action}"
