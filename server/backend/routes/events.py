from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request

from core.event_store import read_events, seed_demo_events_if_empty


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
