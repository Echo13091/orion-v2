from __future__ import annotations

from typing import Any

from core.state import get_state_snapshot
from memory.memory import get_baseline, get_recent_trend

# Edge profile: strict symbolic actions. No LLM is used in the background loop.
# Real hardware execution only happens in ai.router behind safety and mode gates.
VALID_ACTIONS = {
    "observe",
    "high_cpu",
    "high_memory",
    "handle_fault",
    "delay_irrigation",
    "skip_irrigation",
    "stop_sprinkler",
}

EXECUTABLE_ACTIONS = {
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


def _decision(
    action: str,
    reason: str,
    *,
    params: dict[str, Any] | None = None,
    source: str = "rules",
    requires_execution: bool | None = None,
) -> dict[str, Any]:
    normalized = (action or "observe").strip().lower()

    if normalized not in VALID_ACTIONS:
        normalized = "observe"
        reason = "Invalid action blocked"
        params = {}
        source = "safety"

    return {
        "action": normalized,
        "reason": reason or "No reason provided",
        "params": params or {},
        "source": source,
        "requires_execution": (normalized in EXECUTABLE_ACTIONS) if requires_execution is None else bool(requires_execution),
    }


# -------------------------
# USER INPUT DECISION
# -------------------------
def decide_user_action(user_input: str | None = None) -> str:
    """Fast rule-based routing for chat.

    Edge rule: common Orion questions should be answered by deterministic
    summaries, not by an LLM. Raw JSON is only returned when explicitly asked.
    """
    text = (user_input or "").lower().strip()

    if not text:
        return "chat"

    raw_requested = any(x in text for x in [
        "raw",
        "json",
        "dump",
        "full state",
        "debug state",
        "complete state",
    ])

    if raw_requested and any(x in text for x in [
        "status",
        "state",
        "system",
        "weather",
        "sprinkler",
        "irrigation",
        "thermostat",
    ]):
        return "get_system_status"

    if any(x in text for x in [
        "what can you control",
        "control capabilities",
        "device capabilities",
        "what devices",
    ]):
        return "control_help"

    # Commands must still go through the proven device-control path.
    device_terms = [
        "sprinkler",
        "irrigation",
        "watering",
        "water zone",
        "zone",
        "thermostat",
        "hvac",
        "fan",
        "setpoint",
    ]

    control_terms = [
        "run",
        "start",
        "stop",
        "force off",
        "turn on",
        "turn off",
        "set ",
        "setpoint",
        "change",
        "apply",
        "skip next",
        "delay irrigation",
        "schedule",
        "program",
        "mode",
        "cool mode",
        "heat mode",
        "auto mode",
        "fan on",
        "fan off",
    ]

    if any(term in text for term in device_terms) and any(term in text for term in control_terms):
        return "device_control"

    # Deterministic user-facing summaries.
    if any(x in text for x in [
        "recommendation",
        "why is irrigation delayed",
        "why irrigation",
        "why is watering delayed",
        "why watering",
        "explain delay",
        "explain irrigation",
    ]):
        return "recommendation_summary"

    if any(x in text for x in [
        "weather",
        "rain",
        "forecast",
        "outside temp",
        "outside temperature",
        "outside humidity",
        "is it raining",
        "will it rain",
        "explain current weather",
        "current weather state",
    ]):
        return "weather_summary"

    if any(x in text for x in [
        "sprinkler status",
        "show sprinkler",
        "irrigation status",
        "watering status",
        "is sprinkler running",
        "is watering running",
    ]):
        return "sprinkler_summary"

    if any(x in text for x in [
        "thermostat status",
        "hvac status",
        "current temperature",
        "inside temperature",
        "indoor temperature",
        "fan status",
    ]):
        return "thermostat_summary"

    if any(x in text for x in [
        "system health",
        "health",
        "status",
        "system status",
        "check home system",
        "check system",
    ]):
        return "system_summary"

    if "bitcoin" in text or "strategy" in text:
        return "run_backtest"

    if any(x in text for x in [
        "deepseek",
        "deep seek",
        "coding model",
        "code model",
        "use deepseek",
        "use deep seek",
        "use the coding model",
        "switch to deepseek",
        "switch to deep seek",
    ]):
        return "code"

    if any(x in text for x in [
        "code",
        "python",
        "function",
        "fix",
        "debug",
        "error",
        "exception",
        "traceback",
        "api",
        "flask",
        "typescript",
        "javascript",
        "tsx",
        "react",
        "next.js",
        "nextjs",
        "gpio",
        "pwm",
        "servo",
        "arduino",
        "raspberry pi",
        "rpi",
        "node",
        "mqtt",
    ]):
        return "code"

    return "chat"


# -------------------------
# BACKGROUND AI DECISION
# -------------------------
def decide_background_action() -> dict[str, Any]:
    """Return a structured, bounded decision for the background loop.

    Edge rule: no model inference here. The loop is deterministic, fast, and
    safe enough to run on a Raspberry Pi.
    """
    state = get_state_snapshot()

    cpu = _safe_float(state.get("cpu"))
    memory = _safe_float(state.get("memory"))
    gpu = _safe_float(state.get("gpu"))
    fault = state.get("fault")

    weather = state.get("weather") or {}
    weather_online = _safe_bool(weather.get("online"))
    weather_condition = weather.get("condition") or "unknown"
    rain_chance_value = _safe_float(weather.get("rain_chance"))

    sprinkler = state.get("sprinkler") or {}
    sprinkler_online = _safe_bool(sprinkler.get("online"))
    sprinkler_running = _sprinkler_running(sprinkler)
    sprinkler_zone = sprinkler.get("zone") or sprinkler.get("active_zone")

    schedule = state.get("irrigation_schedule") or {}
    skip_next_run = _safe_bool(schedule.get("skip_next_run"))

    # Hard safety always wins.
    if fault:
        return _decision(
            "handle_fault",
            "Existing system fault detected",
            params={"fault": fault},
            source="safety",
        )

    # Manual override lock: user-started watering should not be interrupted by
    # autonomous decisions for a short safety window.
    manual_until = _safe_float(state.get("manual_override_until"), 0.0)
    now_value = __import__("time").time()
    if manual_until and manual_until > now_value:
        remaining = max(0, int(manual_until - now_value))
        return _decision(
            "observe",
            f"Manual override active ({remaining}s remaining)",
            params={"manual_override_remaining_seconds": remaining},
            source="manual_override",
            requires_execution=False,
        )

    # If the sprinkler controller reports a manual run, monitor but do not
    # override it automatically. This protects intentional human operation even
    # if it was started outside Orion.
    sprinkler_mode = str(sprinkler.get("mode") or "").strip().lower()
    if sprinkler_running and sprinkler_mode in {"manual", "manual-program", "manual_program"}:
        return _decision(
            "observe",
            "Manual sprinkler run detected; automation is paused",
            params={"zone": sprinkler_zone, "mode": sprinkler_mode},
            source="manual_override",
            requires_execution=False,
        )

    # Weather-aware irrigation control.
    if weather_online and rain_chance_value >= 70 and sprinkler_online and sprinkler_running:
        return _decision(
            "stop_sprinkler",
            f"Rain likely ({rain_chance_value:.0f}%) while sprinkler is running",
            params={"rain_chance": rain_chance_value, "zone": sprinkler_zone},
            source="rules",
        )

    if weather_online and rain_chance_value >= 70:
        if skip_next_run:
            return _decision(
                "observe",
                f"Rain likely ({rain_chance_value:.0f}%). Next irrigation run is already skipped; no sprinkler output is active.",
                params={"rain_chance": rain_chance_value},
                source="rules",
                requires_execution=False,
            )

        return _decision(
            "delay_irrigation",
            f"Rain likely ({rain_chance_value:.0f}%). Skip or delay the next irrigation run.",
            params={"rain_chance": rain_chance_value},
            source="rules",
        )

    # Lightweight anomaly checks.
    try:
        baseline = get_baseline()
    except Exception:
        baseline = {"cpu_avg": 0.0, "mem_avg": 0.0}

    try:
        trend = get_recent_trend()
    except Exception:
        trend = "trend unavailable"

    cpu_avg = _safe_float(baseline.get("cpu_avg"))
    mem_avg = _safe_float(baseline.get("mem_avg"))

    cpu_delta = cpu - cpu_avg
    mem_delta = memory - mem_avg

    if cpu_delta > 20:
        return _decision(
            "high_cpu",
            f"CPU spike (+{cpu_delta:.1f}%)",
            params={"cpu": cpu, "cpu_avg": cpu_avg, "trend": trend},
            source="rules",
        )

    if mem_delta > 25:
        return _decision(
            "high_memory",
            f"Memory spike (+{mem_delta:.1f}%)",
            params={"memory": memory, "mem_avg": mem_avg, "trend": trend},
            source="rules",
        )

    if gpu > 85:
        return _decision(
            "observe",
            f"GPU high ({gpu:.1f}%)",
            params={"gpu": gpu, "trend": trend},
            source="rules",
        )

    return _decision(
        "observe",
        (
            f"Monitoring. CPU {cpu:.1f}% | MEM {memory:.1f}% | "
            f"GPU {gpu:.1f}% | WEATHER {weather_condition} | RAIN {rain_chance_value:.0f}%"
        ),
        params={
            "cpu": cpu,
            "memory": memory,
            "gpu": gpu,
            "rain_chance": rain_chance_value,
            "trend": trend,
        },
        source="rules",
    )
