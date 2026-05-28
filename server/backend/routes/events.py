from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request

from core.event_store import read_events, seed_demo_events_if_empty
from core.state import get_state_snapshot


events_bp = Blueprint("events", __name__, url_prefix="/v1")


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
        "compact",
    }


def _is_fault_event(event: dict[str, Any]) -> bool:
    return (
        event.get("severity") in {"warning", "critical"}
        or event.get("event_type") in {"fault", "node_offline", "policy_block"}
    )


def _compact_event_key(event: dict[str, Any]) -> str:
    return "::".join(
        [
            str(event.get("subsystem") or ""),
            str(event.get("node") or ""),
            str(event.get("severity") or ""),
            str(event.get("event_type") or ""),
            str(event.get("message") or ""),
            str(event.get("source") or ""),
        ]
    )


def _compact_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compacted: dict[str, dict[str, Any]] = {}

    for event in events:
        key = _compact_event_key(event)
        timestamp = float(event.get("timestamp") or 0)
        existing = compacted.get(key)

        if existing is None:
            compacted_event = dict(event)
            compacted_event["repeat_count"] = 1
            compacted_event["first_seen"] = timestamp
            compacted_event["latest_seen"] = timestamp
            compacted_event["latest_event_id"] = event.get("id")
            compacted[key] = compacted_event
            continue

        repeat_count = int(existing.get("repeat_count") or 1) + 1
        first_seen = min(float(existing.get("first_seen") or timestamp), timestamp)
        latest_seen = max(float(existing.get("latest_seen") or timestamp), timestamp)

        if timestamp >= float(existing.get("timestamp") or 0):
            newest = dict(event)
            newest["repeat_count"] = repeat_count
            newest["first_seen"] = first_seen
            newest["latest_seen"] = latest_seen
            newest["latest_event_id"] = event.get("id")
            compacted[key] = newest
        else:
            existing["repeat_count"] = repeat_count
            existing["first_seen"] = first_seen
            existing["latest_seen"] = latest_seen

    return sorted(
        compacted.values(),
        key=lambda item: float(item.get("latest_seen") or item.get("timestamp") or 0),
        reverse=True,
    )


def _fault_key(event: dict[str, Any]) -> str:
    return "::".join(
        [
            str(event.get("subsystem") or ""),
            str(event.get("node") or ""),
            str(event.get("event_type") or ""),
            str(event.get("message") or ""),
        ]
    )


def _recovery_key(event: dict[str, Any]) -> str:
    subsystem = str(event.get("subsystem") or "")
    node = str(event.get("node") or "")
    event_type = str(event.get("event_type") or "")

    if event_type == "node_recovered":
        return "::".join([subsystem, node, "node_offline"])

    return "::".join([subsystem, node, event_type])


def _fault_impact(event: dict[str, Any]) -> str:
    subsystem = str(event.get("subsystem") or "")
    event_type = str(event.get("event_type") or "")
    severity = str(event.get("severity") or "")

    if subsystem == "vision" and event_type == "node_offline":
        return (
            "Camera stream, snapshots, lawn condition, and visual rain evidence "
            "are unavailable. Orion continues operating with weather, sprinkler, "
            "thermostat, and event telemetry."
        )

    if event_type == "policy_block":
        return "A policy prevented an unsafe or unavailable action from executing."

    if event_type == "fault":
        return "Subsystem fault detected. Operator review is recommended."

    if severity == "critical":
        return "Critical subsystem condition detected. Operator review is required."

    if severity == "warning":
        return "Warning or degraded condition detected. Orion should use trusted telemetry only."

    return "Operational condition requires review."


def _build_fault_summary(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compacted_faults = _compact_events(
        [event for event in events if _is_fault_event(event)]
    )

    recoveries: dict[str, dict[str, Any]] = {}

    for event in events:
        if str(event.get("event_type") or "") in {"node_recovered", "fault_recovered"}:
            key = _recovery_key(event)
            existing = recoveries.get(key)
            timestamp = float(event.get("timestamp") or 0)

            if not existing or timestamp > float(existing.get("timestamp") or 0):
                recoveries[key] = event

    faults: list[dict[str, Any]] = []

    for event in compacted_faults:
        key = _fault_key(event)
        recovery = recoveries.get(key)

        first_seen = float(event.get("first_seen") or event.get("timestamp") or 0)
        last_seen = float(event.get("latest_seen") or event.get("timestamp") or 0)
        recovered_at = float(recovery.get("timestamp") or 0) if recovery else None

        status = "active"

        if recovered_at and recovered_at >= last_seen:
            status = "recovered"

        faults.append(
            {
                "key": key,
                "subsystem": event.get("subsystem"),
                "node": event.get("node"),
                "status": status,
                "severity": event.get("severity"),
                "event_type": event.get("event_type"),
                "message": event.get("message"),
                "source": event.get("source"),
                "first_seen": first_seen,
                "last_seen": last_seen,
                "repeat_count": event.get("repeat_count", 1),
                "latest_event_id": event.get("latest_event_id") or event.get("id"),
                "recovered_at": recovered_at,
                "recovery_event_id": recovery.get("id") if recovery else None,
                "impact": _fault_impact(event),
                "evidence": event.get("evidence") or {},
            }
        )

    return sorted(
        faults,
        key=lambda item: float(item.get("last_seen") or 0),
        reverse=True,
    )


@events_bp.get("/events")
def get_events():
    seed_demo_events_if_empty()

    limit_raw = request.args.get("limit", "100")
    compact = _truthy(request.args.get("compact"))

    try:
        limit = max(1, min(int(limit_raw), 500))
    except ValueError:
        limit = 100

    subsystem = request.args.get("subsystem") or None
    severity = request.args.get("severity") or None
    event_type = request.args.get("event_type") or None

    raw_limit = 500 if compact else limit

    raw_events = read_events(
        limit=raw_limit,
        subsystem=subsystem,
        severity=severity,
        event_type=event_type,
    )

    events = _compact_events(raw_events)[:limit] if compact else raw_events[:limit]

    active_faults = [event for event in events if _is_fault_event(event)]

    return jsonify(
        {
            "ok": True,
            "compact": compact,
            "count": len(events),
            "raw_count": len(raw_events),
            "active_fault_count": len(active_faults),
            "events": events,
        }
    )


def _live_fault_summary() -> list[dict[str, Any]]:
    state = get_state_snapshot()

    # /v1/faults is event-route code, so it can otherwise read stale controller
    # state if /v1/system has not refreshed the standalone sprinkler yet.
    # Refresh here before calculating live active faults.
    try:
        from api.system import _persist_live_sprinkler_state, _sprinkler_with_live_standalone

        sprinkler_snapshot = state.get("sprinkler") if isinstance(state.get("sprinkler"), dict) else {}
        refreshed_sprinkler = _sprinkler_with_live_standalone(sprinkler_snapshot)
        _persist_live_sprinkler_state(refreshed_sprinkler)
        state = get_state_snapshot()
    except Exception as exc:
        print(f"[OPERATIONS] Failed to refresh sprinkler before live fault summary: {exc}")

    now = float(state.get("last_update") or 0)

    faults: list[dict[str, Any]] = []

    def add_fault(
        *,
        key: str,
        subsystem: str,
        node: str,
        severity: str,
        event_type: str,
        message: str,
        source: str,
        evidence: dict[str, Any] | None = None,
        impact: str | None = None,
    ) -> None:
        faults.append(
            {
                "key": key,
                "subsystem": subsystem,
                "node": node,
                "status": "active",
                "severity": severity,
                "event_type": event_type,
                "message": message,
                "source": source,
                "first_seen": now,
                "last_seen": now,
                "repeat_count": 1,
                "latest_event_id": None,
                "recovered_at": None,
                "recovery_event_id": None,
                "impact": impact or "Current live subsystem state requires operator review.",
                "evidence": evidence or {},
            }
        )

    sprinkler = state.get("sprinkler") if isinstance(state.get("sprinkler"), dict) else {}
    thermostat = state.get("thermostat") if isinstance(state.get("thermostat"), dict) else {}

    global_fault = state.get("fault")
    stale_sprinkler_fault = (
        isinstance(global_fault, str)
        and global_fault.startswith("sprinkler:")
        and sprinkler.get("online") is True
        and sprinkler.get("fault") is not True
    )
    stale_thermostat_fault = (
        isinstance(global_fault, str)
        and global_fault.startswith("thermostat:")
        and thermostat.get("online") is True
        and thermostat.get("fault") is not True
    )

    if global_fault and not stale_sprinkler_fault and not stale_thermostat_fault:
        add_fault(
            key="live::system::fault",
            subsystem="system",
            node="orion",
            severity="critical",
            event_type="fault",
            message=str(global_fault),
            source="live_state",
            evidence={"fault": global_fault},
            impact="Current global Orion fault is active.",
        )

    if sprinkler.get("online") is False or sprinkler.get("fault") is True:
        message = (
            sprinkler.get("fault_message")
            or sprinkler.get("error")
            or "Sprinkler controller unavailable"
        )
        add_fault(
            key="live::irrigation::sprinkler",
            subsystem="irrigation",
            node="sprinkler-controller",
            severity="critical" if sprinkler.get("online") is False else "warning",
            event_type="node_offline" if sprinkler.get("online") is False else "fault",
            message=str(message),
            source="live_state",
            evidence={
                "online": sprinkler.get("online"),
                "fault": sprinkler.get("fault"),
                "fault_code": sprinkler.get("fault_code"),
                "health": sprinkler.get("health"),
            },
            impact="Irrigation automation should not execute until the controller is healthy.",
        )

    thermostat = state.get("thermostat") if isinstance(state.get("thermostat"), dict) else {}
    if thermostat.get("online") is False or thermostat.get("fault") is True:
        message = (
            thermostat.get("fault_message")
            or thermostat.get("error")
            or "Thermostat controller unavailable"
        )
        add_fault(
            key="live::hvac::thermostat",
            subsystem="hvac",
            node="thermostat-controller",
            severity="critical" if thermostat.get("online") is False else "warning",
            event_type="node_offline" if thermostat.get("online") is False else "fault",
            message=str(message),
            source="live_state",
            evidence={
                "online": thermostat.get("online"),
                "fault": thermostat.get("fault"),
                "fault_code": thermostat.get("fault_code"),
                "health": thermostat.get("health"),
            },
            impact="HVAC automation should not execute until the controller is healthy.",
        )

    fault_status = state.get("fault_status") if isinstance(state.get("fault_status"), dict) else {}
    manual_override = fault_status.get("manual_override") if isinstance(fault_status.get("manual_override"), dict) else {}
    if manual_override.get("active"):
        add_fault(
            key="live::automation::manual_override",
            subsystem="automation",
            node="orion-brain",
            severity="warning",
            event_type="policy_block",
            message="Manual override is active",
            source="live_state",
            evidence=manual_override,
            impact="Automatic hardware actions are paused while manual override is active.",
        )

    return faults


@events_bp.get("/faults")
def get_faults():
    seed_demo_events_if_empty()

    include_recovered = _truthy(request.args.get("include_recovered"))
    limit_raw = request.args.get("limit", "500")

    try:
        limit = max(1, min(int(limit_raw), 500))
    except ValueError:
        limit = 500

    live_faults = _live_fault_summary()
    historical_faults = _build_fault_summary(read_events(limit=500))

    if include_recovered:
        recovered_faults = [
            fault
            for fault in historical_faults
            if fault.get("status") == "recovered"
        ]
        faults = live_faults + recovered_faults
    else:
        faults = live_faults

    faults = faults[:limit]

    return jsonify(
        {
            "ok": True,
            "count": len(faults),
            "active_fault_count": len(live_faults),
            "include_recovered": include_recovered,
            "faults": faults,
        }
    )

