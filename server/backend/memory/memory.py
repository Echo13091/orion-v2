from __future__ import annotations

import json
import os
import time
from pathlib import Path
from threading import RLock
from typing import Any

# This file intentionally supports BOTH parts of Orion memory:
# 1) chat/session memory used by api.chat and api.sessions
# 2) system/event memory used by the background AI loop
#
# The previous patch only included system memory helpers, which caused:
# ImportError: cannot import name 'add_message' from 'memory.memory'

BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR.parent

SESSION_FILE = Path(
    os.getenv(
        "ORION_SESSION_MEMORY_FILE",
        str(BASE_DIR / "sessions.json"),
    )
)

# Some older Orion builds kept sessions.json at backend/sessions.json.
LEGACY_ROOT_SESSION_FILE = BACKEND_DIR / "sessions.json"

SYSTEM_FILE = Path(
    os.getenv(
        "ORION_SYSTEM_MEMORY_FILE",
        str(BASE_DIR / "system_memory.json"),
    )
)

MAX_MESSAGES_PER_SESSION = int(os.getenv("ORION_MAX_MESSAGES_PER_SESSION", "200"))
MAX_HISTORY_ITEMS = int(os.getenv("ORION_MEMORY_MAX_HISTORY", "1000"))
MAX_EVENT_ITEMS = int(os.getenv("ORION_MEMORY_MAX_EVENTS", "500"))

_memory_lock = RLock()


# -----------------------------------------------------------------------------
# JSON FILE HELPERS
# -----------------------------------------------------------------------------
def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, default=str))
    except Exception:
        return str(value)


def _backup_corrupt_file(path: Path) -> Path | None:
    if not path.exists():
        return None

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.stem}.corrupt-{timestamp}{path.suffix}")

    try:
        path.replace(backup)
        return backup
    except Exception:
        return None


def _read_json(path: Path, default: Any) -> Any:
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        return default

    try:
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return default
        return json.loads(raw)

    except json.JSONDecodeError as exc:
        backup = _backup_corrupt_file(path)
        print(
            "[MEMORY] Corrupted JSON detected. Starting fresh. "
            f"path={path} error={exc} backup={backup}"
        )
        return default

    except Exception as exc:  # noqa: BLE001
        print(f"[MEMORY] Failed to read JSON. Starting fresh. path={path} error={exc}")
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    safe = _json_safe(data)

    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(safe, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    os.replace(tmp, path)


def _session_path() -> Path:
    # Prefer the current memory/sessions.json if it exists. If it does not exist
    # but an older backend/sessions.json exists, keep using the legacy file so
    # existing saved chats are not silently hidden.
    if SESSION_FILE.exists():
        return SESSION_FILE
    if LEGACY_ROOT_SESSION_FILE.exists():
        return LEGACY_ROOT_SESSION_FILE
    return SESSION_FILE


# -----------------------------------------------------------------------------
# SESSION MEMORY - used by api.chat and api.sessions
# -----------------------------------------------------------------------------
def _default_session(session_id: str | None = None) -> dict[str, Any]:
    title = "New Chat"
    if session_id:
        title = "New Chat"

    return {
        "title": title,
        "messages": [],
        "profile": {
            "name": None,
            "preferences": {},
        },
    }


def _coerce_messages(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []

    messages: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue

        role = str(item.get("role") or "assistant").strip().lower()
        if role not in {"user", "assistant", "system"}:
            role = "assistant"

        content = str(item.get("content") or "")
        messages.append({"role": role, "content": content})

    return messages[-MAX_MESSAGES_PER_SESSION:]


def _coerce_session(value: Any, session_id: str | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return _default_session(session_id)

    profile = value.get("profile") if isinstance(value.get("profile"), dict) else {}
    preferences = profile.get("preferences") if isinstance(profile.get("preferences"), dict) else {}

    return {
        "title": str(value.get("title") or "New Chat"),
        "messages": _coerce_messages(value.get("messages")),
        "profile": {
            "name": profile.get("name"),
            "preferences": preferences,
        },
    }


def _coerce_session_store(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}

    store: dict[str, dict[str, Any]] = {}
    for session_id, session_data in value.items():
        sid = str(session_id)
        store[sid] = _coerce_session(session_data, sid)

    return store


def load_memory() -> dict[str, dict[str, Any]]:
    """Load chat/session memory.

    api.sessions imports this directly, so this function must remain stable.
    """
    with _memory_lock:
        return _coerce_session_store(_read_json(_session_path(), {}))


def save_memory(memory_store: dict[str, Any]) -> None:
    with _memory_lock:
        _write_json(_session_path(), _coerce_session_store(memory_store))


def init_session(memory_store: dict[str, Any], session_id: str) -> None:
    if session_id not in memory_store:
        memory_store[session_id] = _default_session(session_id)
    else:
        memory_store[session_id] = _coerce_session(memory_store[session_id], session_id)


def extract_facts(session_data: dict[str, Any], message: str) -> None:
    lowered = message.lower()
    marker = "my name is "

    if marker in lowered:
        original_index = lowered.index(marker) + len(marker)
        name = message[original_index:].strip()
        if name:
            session_data.setdefault("profile", {}).setdefault("preferences", {})
            session_data["profile"]["name"] = name[:60]


def add_message(session_id: str, role: str, content: str) -> None:
    """Append a chat message.

    api.chat imports this function. Keep the signature exactly:
    add_message(session_id, role, content)
    """
    sid = str(session_id)
    clean_role = str(role or "assistant").strip().lower()
    if clean_role not in {"user", "assistant", "system"}:
        clean_role = "assistant"

    text = str(content or "")

    with _memory_lock:
        memory_store = load_memory()
        init_session(memory_store, sid)

        session_data = memory_store[sid]

        if clean_role == "user":
            extract_facts(session_data, text)

            if session_data.get("title") in {None, "", "New Chat"}:
                trimmed = text.strip()
                if len(trimmed) >= 4:
                    session_data["title"] = trimmed[:60]

        session_data.setdefault("messages", []).append(
            {
                "role": clean_role,
                "content": text,
            }
        )

        session_data["messages"] = _coerce_messages(session_data.get("messages"))
        save_memory(memory_store)


def get_memory(session_id: str) -> dict[str, Any]:
    sid = str(session_id)

    with _memory_lock:
        memory_store = load_memory()
        init_session(memory_store, sid)
        save_memory(memory_store)
        return memory_store[sid]


def rename_session(session_id: str, new_title: str) -> None:
    sid = str(session_id)

    with _memory_lock:
        memory_store = load_memory()
        if sid in memory_store:
            memory_store[sid]["title"] = str(new_title or "Chat").strip() or "Chat"
            save_memory(memory_store)


def delete_session(session_id: str) -> None:
    sid = str(session_id)

    with _memory_lock:
        memory_store = load_memory()
        if sid in memory_store:
            del memory_store[sid]
            save_memory(memory_store)


def clear_memory() -> dict[str, Any]:
    with _memory_lock:
        _write_json(_session_path(), {})
        return {"ok": True, "message": "Session memory cleared", "path": str(_session_path())}


# -----------------------------------------------------------------------------
# SYSTEM MEMORY - used by ai.brain and ai.loop
# -----------------------------------------------------------------------------
def _default_system_memory() -> dict[str, list[dict[str, Any]]]:
    return {
        # Newer format.
        "history": [],
        "events": [],
        # Compatibility with older get_baseline/get_recent_trend expectations.
        "cpu_history": [],
        "memory_history": [],
    }


def _coerce_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    clean: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            safe_item = _json_safe(item)
            if isinstance(safe_item, dict):
                clean.append(safe_item)
    return clean


def _coerce_system_memory(data: Any) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(data, dict):
        return _default_system_memory()

    history = _coerce_list(
        data.get("history")
        or data.get("system_history")
        or data.get("states")
        or []
    )

    cpu_history = _coerce_list(data.get("cpu_history") or [])
    memory_history = _coerce_list(data.get("memory_history") or [])

    # Older Orion stored cpu_history and memory_history separately. Newer code
    # uses history. Build history from old data when needed.
    if not history and cpu_history:
        history = cpu_history

    if not cpu_history and history:
        cpu_history = history

    if not memory_history and history:
        memory_history = history

    events = _coerce_list(data.get("events") or data.get("event_log") or data.get("logs") or [])

    return {
        "history": history[-MAX_HISTORY_ITEMS:],
        "cpu_history": cpu_history[-MAX_HISTORY_ITEMS:],
        "memory_history": memory_history[-MAX_HISTORY_ITEMS:],
        "events": events[-MAX_EVENT_ITEMS:],
    }


def load_system_memory() -> dict[str, list[dict[str, Any]]]:
    """Load trend/event memory safely.

    If JSON is corrupted, it is backed up and replaced with a clean object so
    the background AI loop does not die with JSONDecodeError.
    """
    with _memory_lock:
        return _coerce_system_memory(_read_json(SYSTEM_FILE, _default_system_memory()))


def save_system_memory(data: dict[str, Any]) -> None:
    with _memory_lock:
        _write_json(SYSTEM_FILE, _coerce_system_memory(data))


def log_system_state(cpu: float, memory: float) -> None:
    with _memory_lock:
        data = load_system_memory()

        entry = {
            "time": time.time(),
            "cpu": float(cpu or 0.0),
            "memory": float(memory or 0.0),
        }

        data.setdefault("history", []).append(entry)
        data.setdefault("cpu_history", []).append(entry)
        data.setdefault("memory_history", []).append(entry)

        data["history"] = data["history"][-MAX_HISTORY_ITEMS:]
        data["cpu_history"] = data["cpu_history"][-MAX_HISTORY_ITEMS:]
        data["memory_history"] = data["memory_history"][-MAX_HISTORY_ITEMS:]

        save_system_memory(data)


def log_event(event_type: str, details: dict[str, Any] | None = None) -> None:
    with _memory_lock:
        data = load_system_memory()
        data.setdefault("events", []).append(
            {
                "time": time.time(),
                "type": str(event_type),
                "action": str(event_type),
                "details": _json_safe(details or {}),
                "payload": _json_safe(details or {}),
            }
        )
        data["events"] = data["events"][-MAX_EVENT_ITEMS:]
        save_system_memory(data)


def get_recent_trend() -> str:
    data = load_system_memory()
    history = data.get("history") or data.get("cpu_history") or []

    if len(history) < 2:
        return "warming up"

    latest = history[-1]
    previous = history[max(0, len(history) - 10)]

    try:
        cpu_delta = float(latest.get("cpu", 0.0)) - float(previous.get("cpu", 0.0))
        mem_delta = float(latest.get("memory", 0.0)) - float(previous.get("memory", 0.0))
        return f"cpu_delta={cpu_delta:.1f}%, mem_delta={mem_delta:.1f}%"
    except Exception:
        return "trend unavailable"


def get_baseline() -> dict[str, float]:
    data = load_system_memory()
    history = data.get("history") or data.get("cpu_history") or []

    cpu_values: list[float] = []
    mem_values: list[float] = []

    for item in history[-50:]:
        try:
            cpu_values.append(float(item.get("cpu", 0.0)))
            mem_values.append(float(item.get("memory", 0.0)))
        except Exception:
            continue

    if not cpu_values or not mem_values:
        return {
            "cpu_avg": 0.0,
            "mem_avg": 0.0,
        }

    return {
        "cpu_avg": sum(cpu_values) / len(cpu_values),
        "mem_avg": sum(mem_values) / len(mem_values),
    }


def get_events(limit: int = 50) -> list[dict[str, Any]]:
    data = load_system_memory()
    events = data.get("events", [])
    return events[-max(1, int(limit)):]


def clear_system_memory() -> dict[str, Any]:
    data = _default_system_memory()
    save_system_memory(data)
    return {
        "ok": True,
        "message": "System memory cleared",
        "path": str(SYSTEM_FILE),
    }
