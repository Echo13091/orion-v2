from __future__ import annotations

import os
import time
from typing import Any

from ai.brain import EXECUTABLE_ACTIONS, decide_background_action
from ai.router import execute_background_action
from core.runtime import update_system_metrics
from core.state import get_state_snapshot, update_state
from memory.memory import get_recent_trend, log_event, log_system_state
from tools.device_control import get_irrigation_schedule, run_orion_scheduler_tick

MIN_ACTION_INTERVAL_SECONDS = float(os.getenv("ORION_MIN_ACTION_INTERVAL_SECONDS", "30"))
LOOP_MIN_INTERVAL_SECONDS = float(os.getenv("ORION_LOOP_MIN_INTERVAL_SECONDS", "2.0"))
LOG_EVERY_SECONDS = float(os.getenv("ORION_LOG_EVERY_SECONDS", "10"))
OFFLINE_FAULT_AFTER_POLLS = int(os.getenv("ORION_OFFLINE_FAULT_AFTER_POLLS", "3"))
STUCK_VALVE_GRACE_SECONDS = float(os.getenv("ORION_STUCK_VALVE_GRACE_SECONDS", "20"))


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


def _result_was_hardware_execution(result: Any) -> bool:
    return bool(isinstance(result, dict) and result.get("executed"))


def _already_applied_result(action: str, decision: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "ok": True,
        "executed": False,
        "blocked": False,
        "status": "already_applied",
        "action": action,
        "reason": reason,
        "message": reason,
        "decision": decision,
        "time": time.time(),
    }


def _holding_result(action: str, decision: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "ok": True,
        "executed": False,
        "blocked": False,
        "status": "holding",
        "action": action,
        "reason": reason,
        "message": reason,
        "decision": decision,
        "time": time.time(),
    }


def _safe_log_system_state(cpu: float, memory: float) -> None:
    try:
        log_system_state(cpu, memory)
    except Exception as exc:  # noqa: BLE001
        print(f"[AI] Memory log_system_state failed: {exc}")


def _safe_get_trend() -> str:
    try:
        return get_recent_trend()
    except Exception as exc:  # noqa: BLE001
        print(f"[AI] Memory get_recent_trend failed: {exc}")
        return "trend unavailable"


def _safe_log_event(action: str, payload: dict[str, Any]) -> None:
    try:
        log_event(action, payload)
    except Exception as exc:  # noqa: BLE001
        print(f"[AI] Memory log_event failed: {exc}")




def _manual_override_status(state: dict[str, Any]) -> dict[str, Any]:
    until = float(state.get("manual_override_until") or 0.0)
    remaining = max(0.0, until - time.time()) if until else 0.0
    return {
        "active": remaining > 0,
        "remaining_seconds": remaining,
        "reason": state.get("manual_override_reason"),
        "until": until,
    }


def _run_fault_detection(
    state: dict[str, Any],
    tracker: dict[str, Any],
) -> dict[str, Any]:
    """Lightweight edge fault detection.

    Detects repeated offline device polls and a likely stuck sprinkler valve if
    a stop command was executed but the sprinkler still reports running after
    a grace window. Returns an updated fault_status dictionary.
    """
    now = time.time()
    sprinkler = state.get("sprinkler") or {}
    thermostat = state.get("thermostat") or {}

    tracker["sprinkler_offline_count"] = 0 if sprinkler.get("online") else int(tracker.get("sprinkler_offline_count", 0)) + 1
    tracker["thermostat_offline_count"] = 0 if thermostat.get("online") else int(tracker.get("thermostat_offline_count", 0)) + 1

    fault: str | None = None
    if tracker["sprinkler_offline_count"] >= OFFLINE_FAULT_AFTER_POLLS:
        fault = "sprinkler offline"
    elif tracker["thermostat_offline_count"] >= OFFLINE_FAULT_AFTER_POLLS:
        fault = "thermostat offline"

    last_execution = state.get("last_execution") if isinstance(state.get("last_execution"), dict) else {}
    stop_recently_executed = (
        last_execution.get("action") == "stop_sprinkler"
        and bool(last_execution.get("executed"))
        and bool(last_execution.get("ok", True))
    )

    if stop_recently_executed and _sprinkler_running(sprinkler):
        if not tracker.get("stuck_valve_since"):
            tracker["stuck_valve_since"] = now
        elif now - float(tracker.get("stuck_valve_since") or now) >= STUCK_VALVE_GRACE_SECONDS:
            fault = f"possible stuck valve: sprinkler still running after stop command"
    else:
        tracker["stuck_valve_since"] = None

    fault_status = {
        "sprinkler_offline_count": tracker.get("sprinkler_offline_count", 0),
        "thermostat_offline_count": tracker.get("thermostat_offline_count", 0),
        "stuck_valve_since": tracker.get("stuck_valve_since"),
        "manual_override": _manual_override_status(state),
        "last_fault_check": now,
    }

    update_payload = {"fault_status": fault_status}
    current_fault = state.get("fault")
    if fault:
        update_payload["fault"] = fault
    elif current_fault in {"sprinkler offline", "thermostat offline"} or str(current_fault or "").startswith("possible stuck valve"):
        update_payload["fault"] = None

    update_state(**update_payload)
    return fault_status


def _safe_scheduler_tick(state: dict[str, Any]) -> dict[str, Any] | None:
    try:
        result = run_orion_scheduler_tick(
            weather=state.get("weather") or {},
            sprinkler=state.get("sprinkler") or {},
            automation_mode=str(state.get("automation_mode") or "manual"),
        )

        if isinstance(result, dict) and isinstance(result.get("schedule"), dict):
            update_state(irrigation_schedule=result["schedule"])

        if isinstance(result, dict) and result.get("event") in {
            "run_started",
            "zone_started",
            "zone_running",
            "awaiting_zone_feedback",
            "run_completed",
            "run_skipped",
            "run_skipped_weather",
            "run_aborted_weather",
            "run_start_failed",
            "zone_start_failed",
            "run_blocked_sprinkler_busy",
            "already_processed",
        }:
            update_state(
                last_execution={
                    "ok": bool(result.get("ok", True)),
                    "executed": bool(result.get("executed")),
                    "blocked": False,
                    "action": "orion_scheduler",
                    "hardware_action": "sprinkler.schedule_tick",
                    "status": result.get("event"),
                    "message": result.get("message"),
                    "result": result.get("result"),
                    "time": time.time(),
                }
            )

        return result

    except Exception as exc:  # noqa: BLE001
        print(f"[AI] Orion scheduler tick failed: {exc}")
        return {
            "ok": False,
            "executed": False,
            "event": "scheduler_error",
            "message": str(exc),
        }


def _execution_precheck(
    action: str,
    decision: dict[str, Any],
    state: dict[str, Any],
    last_hardware_action_time: float,
    now: float,
) -> dict[str, Any] | None:
    normalized = "delay_irrigation" if action == "skip_irrigation" else action
    sprinkler = state.get("sprinkler") or {}
    schedule = state.get("irrigation_schedule") or {}

    # If the goal is already true, do not show cooldown/blocked noise.
    if normalized == "delay_irrigation" and bool(schedule.get("skip_next_run")):
        return _already_applied_result(
            normalized,
            decision,
            "Next irrigation run is already marked skipped.",
        )

    if normalized == "stop_sprinkler" and not _sprinkler_running(sprinkler):
        return _already_applied_result(
            normalized,
            decision,
            "Sprinkler is already stopped.",
        )

    elapsed = now - last_hardware_action_time
    if normalized in EXECUTABLE_ACTIONS and elapsed < MIN_ACTION_INTERVAL_SECONDS:
        return _holding_result(
            normalized,
            decision,
            (
                "Cooldown active; no repeat hardware action needed. Wait "
                f"{MIN_ACTION_INTERVAL_SECONDS - elapsed:.1f}s."
            ),
        )

    return None


def ai_loop() -> None:
    """Edge-ready Orion background loop.

    - No LLM calls in the loop.
    - Modest polling interval.
    - Hardware actions are stateful: if already applied, do nothing.
    - Cooldown only affects new hardware actions, not telemetry/decisions.
    - Errors are contained so Thread-1 stays alive.
    """
    last_hardware_action_time = 0.0
    last_log_time = 0.0
    fault_tracker: dict[str, Any] = {
        "sprinkler_offline_count": 0,
        "thermostat_offline_count": 0,
        "stuck_valve_since": None,
    }

    while True:
        loop_started = time.time()

        try:
            try:
                update_system_metrics()
            except Exception as exc:  # noqa: BLE001
                print(f"[AI] update_system_metrics failed: {exc}")
                update_state(
                    ai_status="error",
                    last_decision={
                        "action": "loop_error",
                        "reason": f"Metrics update failed: {exc}",
                        "result": {"ok": False, "error": str(exc)},
                        "time": time.time(),
                    },
                )
                time.sleep(LOOP_MIN_INTERVAL_SECONDS)
                continue

            now = time.time()
            state = get_state_snapshot()
            cpu = float(state.get("cpu") or 0.0)
            memory = float(state.get("memory") or 0.0)

            # Orion owns irrigation scheduling. This tick is non-blocking: it
            # starts at most one zone and lets the sprinkler controller handle
            # the zone timer. It never calls a hardware schedule endpoint.
            _safe_scheduler_tick(state)
            state = get_state_snapshot()

            _run_fault_detection(state, fault_tracker)
            state = get_state_snapshot()

            if now - last_log_time >= LOG_EVERY_SECONDS:
                _safe_log_system_state(cpu, memory)
                last_log_time = now

            trend = _safe_get_trend()

            try:
                decision = decide_background_action()
            except Exception as exc:  # noqa: BLE001
                print(f"[AI] decide_background_action failed: {exc}")
                decision = {
                    "action": "observe",
                    "reason": f"Decision error: {exc}",
                    "params": {},
                    "source": "loop_error",
                    "requires_execution": False,
                }

            action = str(decision.get("action") or "observe").strip().lower()
            reason = decision.get("reason") or "No reason provided"

            precheck = _execution_precheck(action, decision, state, last_hardware_action_time, now)
            if precheck is not None:
                result = precheck
            else:
                try:
                    result = execute_background_action(decision, state)
                except Exception as exc:  # noqa: BLE001
                    print(f"[AI] execute_background_action failed: {exc}")
                    result = {
                        "ok": False,
                        "executed": False,
                        "blocked": True,
                        "action": action,
                        "reason": f"Execution error: {exc}",
                        "decision": decision,
                        "time": now,
                    }

            if _result_was_hardware_execution(result):
                last_hardware_action_time = now

            _safe_log_event(
                action,
                {
                    "reason": reason,
                    "trend": trend,
                    "cpu": cpu,
                    "memory": memory,
                    "automation_mode": state.get("automation_mode"),
                    "result": result,
                },
            )

            update_state(
                ai_status="active",
                mode="monitoring",
                last_execution=(
                    result if _result_was_hardware_execution(result) else state.get("last_execution")
                ),
                last_decision={
                    "action": action,
                    "reason": reason,
                    "params": decision.get("params", {}),
                    "source": decision.get("source", "unknown"),
                    "requires_execution": decision.get("requires_execution", False),
                    "result": result,
                    "trend": trend,
                    "cpu": cpu,
                    "memory": memory,
                    "time": now,
                },
            )

            latest = get_state_snapshot()
            if (
                latest.get("fault")
                and float(latest.get("cpu") or 0.0) < 60
                and float(latest.get("memory") or 0.0) < 70
                and not str(latest.get("fault")).startswith("manual:")
            ):
                update_state(
                    fault=None,
                    ai_status="active",
                    mode="monitoring",
                    last_decision={
                        "action": "recover",
                        "reason": "System stabilized",
                        "result": "✅ Recovered",
                        "trend": trend,
                        "time": time.time(),
                    },
                )

        except Exception as exc:  # noqa: BLE001
            print(f"[AI] Loop iteration failed: {exc}")
            try:
                update_state(
                    ai_status="error",
                    last_decision={
                        "action": "loop_error",
                        "reason": str(exc),
                        "result": {"ok": False, "error": str(exc)},
                        "time": time.time(),
                    },
                )
            except Exception:
                pass

        elapsed = time.time() - loop_started
        time.sleep(max(0.25, LOOP_MIN_INTERVAL_SECONDS - elapsed))
