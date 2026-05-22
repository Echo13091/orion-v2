from __future__ import annotations

from flask import Blueprint, jsonify, request

from core.event_store import read_events, seed_demo_events_if_empty


events_bp = Blueprint("events", __name__, url_prefix="/v1")


@events_bp.get("/events")
def get_events():
    seed_demo_events_if_empty()

    limit_raw = request.args.get("limit", "100")

    try:
        limit = max(1, min(int(limit_raw), 500))
    except ValueError:
        limit = 100

    subsystem = request.args.get("subsystem") or None
    severity = request.args.get("severity") or None
    event_type = request.args.get("event_type") or None

    events = read_events(
        limit=limit,
        subsystem=subsystem,
        severity=severity,
        event_type=event_type,
    )

    active_faults = [
        event
        for event in events
        if event.get("severity") in {"warning", "critical"}
        or event.get("event_type") in {"fault", "node_offline", "policy_block"}
    ]

    return jsonify(
        {
            "ok": True,
            "count": len(events),
            "active_fault_count": len(active_faults),
            "events": events,
        }
    )
