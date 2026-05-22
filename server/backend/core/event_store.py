from __future__ import annotations

import json
import os
import time
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional


EVENT_LOG_PATH = Path(
    os.getenv(
        "ORION_EVENT_LOG_PATH",
        "/tmp/orion_events.jsonl",
    )
)


_SEED_LOCK = threading.Lock()
_SEEDED_EVENT_KEYS = {
    ("system", "startup", "event_store"),
    ("irrigation", "policy_block", "automation_policy"),
    ("hvac", "safety_policy", "safety_policy"),
}


def now_ts() -> float:
    return time.time()


def make_event(
    *,
    subsystem: str,
    event_type: str,
    message: str,
    severity: str = "info",
    node: Optional[str] = None,
    source: str = "orion",
    evidence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "id": f"evt_{uuid.uuid4().hex[:12]}",
        "timestamp": now_ts(),
        "subsystem": subsystem,
        "node": node or subsystem,
        "severity": severity,
        "event_type": event_type,
        "message": message,
        "source": source,
        "evidence": evidence or {},
    }


def append_event(event: Dict[str, Any]) -> Dict[str, Any]:
    EVENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    with EVENT_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")

    return event


def record_event(
    *,
    subsystem: str,
    event_type: str,
    message: str,
    severity: str = "info",
    node: Optional[str] = None,
    source: str = "orion",
    evidence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    event = make_event(
        subsystem=subsystem,
        event_type=event_type,
        message=message,
        severity=severity,
        node=node,
        source=source,
        evidence=evidence,
    )
    return append_event(event)


def _seed_events_already_present() -> bool:
    existing = read_events(limit=500)

    existing_keys = {
        (
            str(event.get("subsystem", "")),
            str(event.get("event_type", "")),
            str(event.get("source", "")),
        )
        for event in existing
    }

    return _SEEDED_EVENT_KEYS.issubset(existing_keys)


def read_events(
    *,
    limit: int = 100,
    subsystem: Optional[str] = None,
    severity: Optional[str] = None,
    event_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if not EVENT_LOG_PATH.exists():
        return []

    events: List[Dict[str, Any]] = []

    with EVENT_LOG_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            if subsystem and event.get("subsystem") != subsystem:
                continue

            if severity and event.get("severity") != severity:
                continue

            if event_type and event.get("event_type") != event_type:
                continue

            events.append(event)

    events.sort(key=lambda item: item.get("timestamp", 0), reverse=True)
    return events[:limit]


def seed_demo_events_if_empty() -> None:
    """
    Gives the Operations Console useful first-run data without faking live state forever.
    This is intentionally idempotent so concurrent /v1/events requests do not duplicate seed events.
    Safe to remove later once real subsystems are emitting events.
    """
    with _SEED_LOCK:
        if _seed_events_already_present():
            return

        record_event(
            subsystem="system",
            node="orion-server",
            severity="info",
            event_type="startup",
            message="Orion operations event log initialized",
            source="event_store",
            evidence={"event_log_path": str(EVENT_LOG_PATH)},
        )

        record_event(
            subsystem="irrigation",
            node="sprinkler-controller",
            severity="warning",
            event_type="policy_block",
            message="Irrigation may be blocked when weather evidence indicates rain or wet conditions",
            source="automation_policy",
            evidence={
                "policy": "weather_aware_irrigation",
                "reason": "rain_or_wet_condition_guard",
            },
        )

        record_event(
            subsystem="hvac",
            node="hvac-controller",
            severity="info",
            event_type="safety_policy",
            message="HVAC safety policies include changeover lockout and minimum runtime protection",
            source="safety_policy",
            evidence={
                "changeover_lockout": True,
                "minimum_runtime_protection": True,
            },
        )

