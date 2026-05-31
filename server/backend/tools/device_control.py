import json
import os
import re
import time
from pathlib import Path
from typing import Any

import requests


SPRINKLER_BASE_URL = os.getenv(
    "SPRINKLER_BASE_URL",
    "http://sprinkler-controller.local:5000",
).rstrip("/")

THERMOSTAT_BASE_URL = os.getenv(
    "THERMOSTAT_BASE_URL",
    "http://thermostat-controller.local:5002",
).rstrip("/")


SPRINKLER_ZONES = int(os.getenv("SPRINKLER_ZONES", "8"))

# Sprinkler UI uses Zone 1-8.
# sprinkler_v3 routes use zero-based indexes:
# user zone 5 -> /on/4
SPRINKLER_ZONE_OFFSET = int(os.getenv("SPRINKLER_ZONE_OFFSET", "-1"))

MAX_ZONE_MINUTES = 30
MIN_ZONE_MINUTES = 1

MIN_SETPOINT = 50
MAX_SETPOINT = 90

VALID_HVAC_MODES = {"off", "cool", "heat", "auto"}
VALID_FAN_MODES = {"on", "off", "auto"}

SCHEDULE_FILE = Path(os.getenv("ORION_SPRINKLER_SCHEDULE_FILE", "sprinkler_schedule.json"))
VALID_DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_ALIASES = {
    "monday": "mon",
    "mon": "mon",
    "tuesday": "tue",
    "tue": "tue",
    "tues": "tue",
    "wednesday": "wed",
    "wed": "wed",
    "thursday": "thu",
    "thu": "thu",
    "thur": "thu",
    "thurs": "thu",
    "friday": "fri",
    "fri": "fri",
    "saturday": "sat",
    "sat": "sat",
    "sunday": "sun",
    "sun": "sun",
}


# Scheduler execution knobs. Orion owns scheduling and treats the sprinkler
# node as an actuator. The schedule trigger has a small grace window so a
# slightly delayed loop tick does not miss a run, but it will not start hours
# late after a reboot.
SCHEDULE_START_GRACE_SECONDS = float(os.getenv("ORION_SCHEDULE_START_GRACE_SECONDS", "120"))
ZONE_COMPLETION_BUFFER_SECONDS = float(os.getenv("ORION_ZONE_COMPLETION_BUFFER_SECONDS", "5"))
ZONE_MIN_FEEDBACK_SECONDS = float(os.getenv("ORION_ZONE_MIN_FEEDBACK_SECONDS", "5"))

DEFAULT_IRRIGATION_SCHEDULE: dict[str, Any] = {
    "enabled": True,
    "controller": "auto",
    "hardware_sync_required": True,
    "days": VALID_DAYS.copy(),
    "start_time": "06:00",
    "duration_minutes": 10,
    "zones": list(range(1, SPRINKLER_ZONES + 1)),
    "skip_next_run": False,
    "skip_reason": None,
    "skip_if_rain_likely": True,
    "last_run_key": None,
    "active_run": None,
    "last_scheduler_event": None,
    "updated_at": None,
    "hardware_synced": False,
    "hardware_result": {
        "ok": False,
        "message": "No hardware schedule sync attempted yet.",
    },
}



# -------------------------
# ORION MANUAL OVERRIDE LOCK
# -------------------------
def _set_manual_override(reason: str) -> None:
    """Pause autonomous sprinkler decisions after a user/manual start.

    Imported lazily to avoid coupling the actuator layer to the global state
    module at import time. Scheduler calls pass manual_override=False so
    scheduled zone sequencing does not keep extending the lock.
    """
    try:
        from core.state import set_manual_override_lock

        set_manual_override_lock(reason)
    except Exception as exc:  # noqa: BLE001
        print(f"[CONTROL] manual override lock failed: {exc}")


# -------------------------
# LOW-LEVEL HTTP HELPERS
# -------------------------
def _safe_json_response(response: requests.Response) -> dict[str, Any]:
    try:
        return response.json()
    except Exception:
        return {
            "status_code": response.status_code,
            "text": response.text[:500],
        }



def _is_expected_sprinkler_redirect(
    *,
    base_url: str,
    path: str,
    response: requests.Response,
) -> bool:
    """
    Some simple Flask-style sprinkler controller routes perform the action and
    redirect back to the controller index page. For sprinkler /on/... commands,
    that redirect is treated as an accepted controller acknowledgement.
    """
    if base_url.rstrip("/") != SPRINKLER_BASE_URL:
        return False

    if response.status_code not in {301, 302, 303, 307, 308}:
        return False

    normalized_path = str(path or "").strip()

    return normalized_path.startswith("/on/")

def _post_json(
    base_url: str,
    path: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 8.0,
) -> dict[str, Any]:
    url = f"{base_url}{path}"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            url,
            json=payload or {},
            headers=headers,
            timeout=timeout,
            allow_redirects=False,
        )

        if 200 <= response.status_code < 300:
            return {
                "ok": True,
                "url": url,
                "payload": payload or {},
                "response": _safe_json_response(response),
            }

        if _is_expected_sprinkler_redirect(
            base_url=base_url,
            path=path,
            response=response,
        ):
            return {
                "ok": True,
                "url": url,
                "payload": payload or {},
                "status": response.status_code,
                "normalized_status": "accepted_redirect",
                "controller_acknowledged": True,
                "location": response.headers.get("Location"),
                "response": response.text[:500],
            }

        return {
            "ok": False,
            "url": url,
            "payload": payload or {},
            "status": response.status_code,
            "response": response.text[:500],
        }

    except Exception as e:
        return {
            "ok": False,
            "url": url,
            "payload": payload or {},
            "error": str(e),
        }


def _post_candidates(
    base_url: str,
    candidates: list[tuple[str, dict[str, Any]]],
    timeout: float = 8.0,
) -> dict[str, Any]:
    errors = []

    for path, payload in candidates:
        result = _post_json(
            base_url=base_url,
            path=path,
            payload=payload,
            timeout=timeout,
        )

        if result.get("ok"):
            return result

        errors.append(result)

    return {
        "ok": False,
        "error": "No control endpoint accepted the command",
        "attempts": errors,
    }


def _request_json(
    method: str,
    base_url: str,
    path: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 8.0,
) -> dict[str, Any]:
    url = f"{base_url}{path}"
    method = method.upper().strip()

    try:
        response = requests.request(
            method,
            url,
            json=payload or {},
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=timeout,
            allow_redirects=False,
        )

        if 200 <= response.status_code < 300:
            return {
                "ok": True,
                "method": method,
                "url": url,
                "payload": payload or {},
                "response": _safe_json_response(response),
            }

        if _is_expected_sprinkler_redirect(
            base_url=base_url,
            path=path,
            response=response,
        ):
            return {
                "ok": True,
                "method": method,
                "url": url,
                "payload": payload or {},
                "status": response.status_code,
                "normalized_status": "accepted_redirect",
                "controller_acknowledged": True,
                "location": response.headers.get("Location"),
                "response": response.text[:500],
            }

        return {
            "ok": False,
            "method": method,
            "url": url,
            "payload": payload or {},
            "status": response.status_code,
            "response": response.text[:500],
        }

    except Exception as e:
        return {
            "ok": False,
            "method": method,
            "url": url,
            "payload": payload or {},
            "error": str(e),
        }


def _request_candidates(
    base_url: str,
    candidates: list[tuple[str, str, dict[str, Any] | None]],
    timeout: float = 8.0,
) -> dict[str, Any]:
    errors = []

    for method, path, payload in candidates:
        result = _request_json(
            method=method,
            base_url=base_url,
            path=path,
            payload=payload or {},
            timeout=timeout,
        )

        if result.get("ok"):
            return result

        errors.append(result)

    return {
        "ok": False,
        "error": "No candidate endpoint accepted the command",
        "attempts": errors,
    }


def _get_status(
    base_url: str,
    candidates: list[str],
    timeout: float = 3.0,
) -> dict[str, Any]:
    errors = []

    for path in candidates:
        url = f"{base_url}{path}"

        try:
            response = requests.get(
                url,
                headers={"Accept": "application/json"},
                timeout=timeout,
            )

            if 200 <= response.status_code < 300:
                return {
                    "ok": True,
                    "url": url,
                    "response": _safe_json_response(response),
                }

            errors.append(
                {
                    "url": url,
                    "status": response.status_code,
                    "response": response.text[:500],
                }
            )

        except Exception as e:
            errors.append(
                {
                    "url": url,
                    "error": str(e),
                }
            )

    return {
        "ok": False,
        "error": "No status endpoint responded",
        "attempts": errors,
    }


# -------------------------
# PARSERS
# -------------------------
def _extract_zone(text: str) -> int | None:
    match = re.search(r"\bzone\s*(\d+)\b", text, re.IGNORECASE)
    if not match:
        return None

    zone = int(match.group(1))

    if zone < 1 or zone > SPRINKLER_ZONES:
        return None

    return zone


def _extract_minutes(text: str, default: int = 1) -> int:
    patterns = [
        r"\bfor\s+(\d+)\s*(?:minute|minutes|min|mins|m|mi|mir)?\b",
        r"\b(\d+)\s*(?:minute|minutes|min|mins|m|mi|mir)\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            minutes = int(match.group(1))
            return max(MIN_ZONE_MINUTES, min(MAX_ZONE_MINUTES, minutes))

    return default


def _extract_setpoint(text: str) -> int | None:
    patterns = [
        r"\bset(?:point)?\s*(?:to)?\s*(\d+)\b",
        r"\btemp(?:erature)?\s*(?:to)?\s*(\d+)\b",
        r"\bthermostat\s*(?:to)?\s*(\d+)\b",
        r"\b(\d+)\s*(?:degrees|degree|f)\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = int(match.group(1))
            if MIN_SETPOINT <= value <= MAX_SETPOINT:
                return value

    return None


def _extract_hvac_mode(text: str) -> str | None:
    lowered = text.lower()

    if "cool" in lowered or "cooling" in lowered:
        return "cool"

    if "heat" in lowered or "heating" in lowered:
        return "heat"

    if "auto" in lowered:
        return "auto"

    if "off" in lowered or "turn hvac off" in lowered:
        return "off"

    return None


def _extract_fan_mode(text: str) -> str | None:
    lowered = text.lower()

    if "fan on" in lowered or "turn fan on" in lowered:
        return "on"

    if "fan off" in lowered or "turn fan off" in lowered:
        return "off"

    if "fan auto" in lowered:
        return "auto"

    return None


def _api_zone(user_zone: int) -> int:
    return int(user_zone) + SPRINKLER_ZONE_OFFSET


def _is_sprinkler_running(status_data: dict[str, Any]) -> bool:
    if status_data.get("running"):
        return True

    if status_data.get("is_running"):
        return True

    if status_data.get("active"):
        return True

    if status_data.get("cycle_running"):
        return True

    zones = status_data.get("zones")
    if isinstance(zones, list) and any(bool(x) for x in zones):
        return True

    return False


# -------------------------
# SPRINKLER CONTROL
# -------------------------
def get_sprinkler_status() -> dict[str, Any]:
    return _get_status(
        SPRINKLER_BASE_URL,
        [
            "/api/status",
        ],
    )


def run_sprinkler_zone(zone: int, minutes: int = 1, *, manual_override: bool = True) -> dict[str, Any]:
    if zone < 1 or zone > SPRINKLER_ZONES:
        return {
            "ok": False,
            "error": f"Invalid zone. Zone must be 1-{SPRINKLER_ZONES}.",
        }

    minutes = max(MIN_ZONE_MINUTES, min(MAX_ZONE_MINUTES, int(minutes)))
    api_zone = _api_zone(zone)

    if api_zone < 0 or api_zone >= SPRINKLER_ZONES:
        return {
            "ok": False,
            "error": f"Invalid API zone calculated from zone {zone}: {api_zone}",
        }

    status = get_sprinkler_status()

    if not status.get("ok"):
        return {
            "ok": False,
            "error": "Cannot verify sprinkler status. Refusing to start a zone.",
            "status": status,
        }

    data = status.get("response", {})
    if _is_sprinkler_running(data):
        return {
            "ok": False,
            "error": "Sprinkler is already running. Stop it before starting another zone.",
            "status": data,
        }

    payload = {
        "minutes": minutes,
    }

    result = _post_json(
        SPRINKLER_BASE_URL,
        f"/on/{api_zone}",
        payload=payload,
        timeout=8.0,
    )

    if result.get("ok"):
        if manual_override:
            _set_manual_override(f"Manual zone {zone} started for {minutes} minute(s)")
        return {
            "ok": True,
            "action": f"Zone {zone} started for {minutes} minute(s)",
            "zone": zone,
            "api_zone": api_zone,
            "minutes": minutes,
            "seconds": minutes * 60,
            "result": result,
        }

    return result


def stop_sprinkler_zone(zone: int) -> dict[str, Any]:
    if zone < 1 or zone > SPRINKLER_ZONES:
        return {
            "ok": False,
            "error": f"Invalid zone. Zone must be 1-{SPRINKLER_ZONES}.",
        }

    api_zone = _api_zone(zone)

    if api_zone < 0 or api_zone >= SPRINKLER_ZONES:
        return {
            "ok": False,
            "error": f"Invalid API zone calculated from zone {zone}: {api_zone}",
        }

    return _post_json(
        SPRINKLER_BASE_URL,
        f"/off/{api_zone}",
        payload={},
        timeout=8.0,
    )


def stop_sprinkler() -> dict[str, Any]:
    """Stop all active sprinkler watering.

    Different local sprinkler builds expose stop as different routes/methods.
    This tries the known V3 route first, then safe fallback candidates.
    """
    return _request_candidates(
        SPRINKLER_BASE_URL,
        [
            ("POST", "/off/0", {}),
            ("GET", "/off/0", {}),
            ("POST", "/off", {}),
            ("GET", "/off", {}),
            ("POST", "/api/stop", {}),
            ("GET", "/api/stop", {}),
            ("POST", "/api/sprinkler/stop", {}),
            ("GET", "/api/sprinkler/stop", {}),
            ("POST", "/stop", {}),
            ("GET", "/stop", {}),
            ("POST", "/stop_all", {}),
            ("GET", "/stop_all", {}),
            ("POST", "/api/stop_all", {}),
            ("GET", "/api/stop_all", {}),
        ],
        timeout=8.0,
    )


def run_sprinkler_program_now(*, manual_override: bool = True) -> dict[str, Any]:
    status = get_sprinkler_status()

    if not status.get("ok"):
        return {
            "ok": False,
            "error": "Cannot verify sprinkler status. Refusing to start program.",
            "status": status,
        }

    data = status.get("response", {})
    if _is_sprinkler_running(data):
        return {
            "ok": False,
            "error": "Sprinkler is already running.",
            "status": data,
        }

    result = _post_json(
        SPRINKLER_BASE_URL,
        "/run_cycle",
        payload={},
        timeout=8.0,
    )
    if result.get("ok") and manual_override:
        _set_manual_override("Manual irrigation cycle started")
    return result


# -------------------------
# SPRINKLER SCHEDULE CONTROL
# -------------------------
def _load_schedule_file() -> dict[str, Any]:
    if not SCHEDULE_FILE.exists():
        return dict(DEFAULT_IRRIGATION_SCHEDULE)

    try:
        data = json.loads(SCHEDULE_FILE.read_text())
        if not isinstance(data, dict):
            return dict(DEFAULT_IRRIGATION_SCHEDULE)
        merged = dict(DEFAULT_IRRIGATION_SCHEDULE)
        merged.update(data)
        return _normalize_schedule(merged)
    except Exception:
        return dict(DEFAULT_IRRIGATION_SCHEDULE)


def _save_schedule_file(schedule: dict[str, Any]) -> None:
    SCHEDULE_FILE.parent.mkdir(parents=True, exist_ok=True)
    SCHEDULE_FILE.write_text(json.dumps(schedule, indent=2, sort_keys=True))


def _normalize_bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", "enable", "enabled"}:
        return True
    if text in {"0", "false", "no", "off", "disable", "disabled"}:
        return False
    return default


def _normalize_days(value: Any) -> list[str]:
    if value is None or value == "":
        return VALID_DAYS.copy()

    if isinstance(value, str):
        lowered = value.lower().strip()
        if lowered in {"all", "daily", "everyday", "every day"}:
            return VALID_DAYS.copy()
        if lowered in {"weekdays", "weekday", "mon-fri", "monday-friday"}:
            return ["mon", "tue", "wed", "thu", "fri"]
        if lowered in {"weekends", "weekend", "sat-sun"}:
            return ["sat", "sun"]
        parts = re.split(r"[,\s]+", lowered)
    elif isinstance(value, list):
        parts = [str(item).lower().strip() for item in value]
    else:
        parts = [str(value).lower().strip()]

    days: list[str] = []
    for part in parts:
        if not part:
            continue
        normalized = DAY_ALIASES.get(part)
        if normalized and normalized not in days:
            days.append(normalized)

    return days or VALID_DAYS.copy()


def _normalize_zones(value: Any) -> list[int]:
    if value is None or value == "":
        return list(range(1, SPRINKLER_ZONES + 1))

    if isinstance(value, str):
        lowered = value.lower().strip()
        if lowered in {"all", "all zones", "every", "every zone"}:
            return list(range(1, SPRINKLER_ZONES + 1))
        raw_items = re.findall(r"\d+", lowered)
    elif isinstance(value, list):
        raw_items = []
        for item in value:
            raw_items.extend(re.findall(r"\d+", str(item)))
    else:
        raw_items = re.findall(r"\d+", str(value))

    zones: list[int] = []
    for item in raw_items:
        zone = int(item)
        if 1 <= zone <= SPRINKLER_ZONES and zone not in zones:
            zones.append(zone)

    return zones or list(range(1, SPRINKLER_ZONES + 1))


def _normalize_time(value: Any) -> str:
    text = str(value or "06:00").strip().lower()

    match = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$", text)
    if not match:
        return "06:00"

    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridiem = match.group(3)

    if meridiem == "pm" and hour != 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0

    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return "06:00"

    return f"{hour:02d}:{minute:02d}"


def _normalize_schedule(schedule: dict[str, Any]) -> dict[str, Any]:
    duration = schedule.get("duration_minutes", schedule.get("minutes", 10))
    try:
        duration_int = int(duration)
    except Exception:
        duration_int = 10

    duration_int = max(MIN_ZONE_MINUTES, min(MAX_ZONE_MINUTES, duration_int))

    active_run = schedule.get("active_run")
    if active_run is not None and not isinstance(active_run, dict):
        active_run = None

    controller = str(schedule.get("controller", "auto") or "auto").strip().lower()
    if controller not in {"auto", "orion", "sprinkler"}:
        controller = "auto"

    hardware_result = schedule.get("hardware_result")
    if not isinstance(hardware_result, dict):
        hardware_result = {"ok": False, "message": "No hardware schedule sync attempted yet."}

    return {
        "enabled": _normalize_bool(schedule.get("enabled"), True),
        "controller": controller,
        "hardware_sync_required": _normalize_bool(schedule.get("hardware_sync_required"), True),
        "days": _normalize_days(schedule.get("days")),
        "start_time": _normalize_time(schedule.get("start_time", schedule.get("time", "06:00"))),
        "duration_minutes": duration_int,
        "zones": _normalize_zones(schedule.get("zones")),
        "skip_next_run": _normalize_bool(schedule.get("skip_next_run"), False),
        "skip_reason": schedule.get("skip_reason"),
        "skip_if_rain_likely": _normalize_bool(schedule.get("skip_if_rain_likely"), True),
        "last_run_key": schedule.get("last_run_key"),
        "active_run": active_run,
        "last_scheduler_event": schedule.get("last_scheduler_event"),
        "updated_at": schedule.get("updated_at"),
        "hardware_synced": _normalize_bool(schedule.get("hardware_synced"), False),
        "hardware_result": hardware_result,
    }


def get_irrigation_schedule() -> dict[str, Any]:
    return _load_schedule_file()


def _controller_schedule_payload(schedule: dict[str, Any]) -> dict[str, Any]:
    """Payload accepted by the patched sprinkler controller schedule API."""
    return {
        "enabled": bool(schedule.get("enabled", True)),
        "days": list(schedule.get("days") or []),
        "start_time": schedule.get("start_time") or "06:00",
        "time": schedule.get("start_time") or "06:00",
        "duration_minutes": int(schedule.get("duration_minutes") or 10),
        "minutes": int(schedule.get("duration_minutes") or 10),
        "zones": list(schedule.get("zones") or []),
        "skip_next_run": bool(schedule.get("skip_next_run", False)),
        "skip_reason": schedule.get("skip_reason"),
        "controller": "sprinkler",
    }


def _sync_schedule_to_controller(schedule: dict[str, Any]) -> dict[str, Any]:
    """Push Orion's schedule to the sprinkler controller when supported.

    The uploaded sprinkler controller now exposes JSON schedule endpoints. If
    the sync succeeds, the green sprinkler controller becomes the schedule
    executor and Orion will not duplicate scheduled zone starts. If the sync
    fails, Orion falls back to local scheduling.
    """
    payload = _controller_schedule_payload(schedule)
    return _request_candidates(
        SPRINKLER_BASE_URL,
        [
            ("PUT", "/api/schedule", payload),
            ("POST", "/api/schedule", payload),
            ("PUT", "/api/program", payload),
            ("POST", "/api/program", payload),
            ("PUT", "/schedule", payload),
            ("POST", "/schedule", payload),
            ("PUT", "/program", payload),
            ("POST", "/program", payload),
            ("PUT", "/api/irrigation/schedule", payload),
            ("POST", "/api/irrigation/schedule", payload),
            ("PUT", "/api/sprinkler/schedule", payload),
            ("POST", "/api/sprinkler/schedule", payload),
        ],
        timeout=8.0,
    )



def _format_day_list(days: Any) -> str:
    if not isinstance(days, list) or not days:
        return "no days"

    canonical = [str(day).lower().strip() for day in days]
    if canonical == VALID_DAYS:
        return "every day"
    if canonical == ["mon", "tue", "wed", "thu", "fri"]:
        return "weekdays"
    if canonical == ["sat", "sun"]:
        return "weekends"

    names = {
        "mon": "Mon",
        "tue": "Tue",
        "wed": "Wed",
        "thu": "Thu",
        "fri": "Fri",
        "sat": "Sat",
        "sun": "Sun",
    }
    return ", ".join(names.get(day, day) for day in canonical)


def _format_zones(zones: Any) -> str:
    if not isinstance(zones, list) or not zones:
        return "no zones"
    try:
        nums = [int(zone) for zone in zones]
    except Exception:
        return ", ".join(str(zone) for zone in zones)
    if nums == list(range(1, SPRINKLER_ZONES + 1)):
        return f"zones 1-{SPRINKLER_ZONES}"
    return "zones " + ", ".join(str(zone) for zone in nums)


def describe_irrigation_schedule(schedule: dict[str, Any] | None = None) -> str:
    """Human-readable Orion-owned schedule summary."""
    schedule = _normalize_schedule(schedule or get_irrigation_schedule())
    enabled_text = "enabled" if schedule.get("enabled") else "disabled"
    skip_text = " The next scheduled run is marked skipped." if schedule.get("skip_next_run") else ""
    return (
        f"Irrigation schedule {enabled_text}: {_format_day_list(schedule.get('days'))} "
        f"at {schedule.get('start_time')}, {schedule.get('duration_minutes')} minute(s) per zone, "
        f"{_format_zones(schedule.get('zones'))}. "
        f"Controller: {schedule.get('controller', 'auto')}."
        f"{skip_text}"
    )


def set_irrigation_schedule(
    *,
    enabled: Any | None = None,
    days: Any | None = None,
    start_time: Any | None = None,
    duration_minutes: Any | None = None,
    zones: Any | None = None,
    skip_if_rain_likely: Any | None = None,
    sync_hardware: bool = True,
) -> dict[str, Any]:
    """Save the irrigation schedule and sync it to the sprinkler controller.

    If the sprinkler controller accepts the schedule API, it becomes the
    executor for scheduled watering. If not, Orion keeps the schedule locally
    and can execute it as a fallback.
    """
    current = get_irrigation_schedule()

    if enabled is not None:
        current["enabled"] = enabled
    if days is not None:
        current["days"] = days
    if start_time is not None:
        current["start_time"] = start_time
    if duration_minutes is not None:
        current["duration_minutes"] = duration_minutes
    if zones is not None:
        current["zones"] = zones
    if skip_if_rain_likely is not None:
        current["skip_if_rain_likely"] = skip_if_rain_likely

    current["skip_next_run"] = False
    current["skip_reason"] = None
    current["active_run"] = None
    current["updated_at"] = time.time()

    normalized = _normalize_schedule(current)

    sync_result = _sync_schedule_to_controller(normalized) if sync_hardware else {
        "ok": False,
        "message": "Hardware sync disabled for this update.",
    }

    if sync_result.get("ok"):
        normalized["controller"] = "sprinkler"
        normalized["hardware_synced"] = True
        normalized["hardware_sync_required"] = True
        event_message = "Irrigation schedule saved and synced to sprinkler controller."
        note = "Schedule saved in Orion and synced to the green sprinkler controller. The sprinkler controller executes scheduled runs."
    else:
        normalized["controller"] = "orion"
        normalized["hardware_synced"] = False
        normalized["hardware_sync_required"] = True
        event_message = "Irrigation schedule saved in Orion; controller sync failed."
        note = "Schedule saved in Orion. Sprinkler controller sync failed, so Orion can execute scheduled runs as fallback."

    normalized["hardware_result"] = sync_result
    normalized["last_scheduler_event"] = {
        "type": "schedule_saved",
        "time": time.time(),
        "message": event_message,
    }
    _save_schedule_file(normalized)

    summary = describe_irrigation_schedule(normalized)

    return {
        "ok": True,
        "action": "set_irrigation_schedule",
        "message": "Irrigation schedule updated.",
        "summary": summary,
        "schedule": normalized,
        "controller": normalized.get("controller"),
        "hardware_synced": bool(normalized.get("hardware_synced")),
        "hardware_result": normalized.get("hardware_result"),
        "note": note,
    }


def skip_next_irrigation(reason: str = "Skipped by Orion") -> dict[str, Any]:
    """Mark the next Orion-controlled irrigation run skipped.

    If watering is currently active, this also stops the sprinkler using the
    working stop endpoint. No schedule sync is attempted against hardware.
    """
    status = get_sprinkler_status()
    stopped_active = False
    stop_result = None

    if status.get("ok") and _is_sprinkler_running(status.get("response", {})):
        stop_result = stop_sprinkler()
        stopped_active = bool(stop_result.get("ok"))

    schedule = get_irrigation_schedule()
    schedule["skip_next_run"] = True
    schedule["skip_reason"] = reason
    schedule["updated_at"] = time.time()
    sync_result = _sync_schedule_to_controller(schedule)
    schedule["hardware_synced"] = bool(sync_result.get("ok"))
    schedule["hardware_result"] = sync_result
    schedule["controller"] = "sprinkler" if sync_result.get("ok") else "orion"
    schedule["last_scheduler_event"] = {
        "type": "skip_next_run",
        "time": time.time(),
        "message": reason,
    }
    normalized = _normalize_schedule(schedule)
    _save_schedule_file(normalized)

    return {
        "ok": True,
        "action": "skip_next_irrigation",
        "message": "Next irrigation run marked skipped.",
        "summary": describe_irrigation_schedule(normalized),
        "controller": normalized.get("controller"),
        "stopped_active_watering": stopped_active,
        "stop_result": stop_result,
        "schedule": normalized,
        "hardware_synced": bool(normalized.get("hardware_synced")),
        "hardware_result": normalized.get("hardware_result"),
        "note": "Next scheduled irrigation run marked skipped. If controller sync succeeded, the sprinkler controller will consume this skip.",
    }


def clear_skip_next_irrigation() -> dict[str, Any]:
    schedule = get_irrigation_schedule()
    schedule["skip_next_run"] = False
    schedule["skip_reason"] = None
    schedule["updated_at"] = time.time()
    schedule["last_scheduler_event"] = {
        "type": "skip_cleared",
        "time": time.time(),
        "message": "Next-run skip cleared.",
    }
    normalized = _normalize_schedule(schedule)
    _save_schedule_file(normalized)
    return {
        "ok": True,
        "action": "clear_skip_next_irrigation",
        "schedule": normalized,
    }




def consume_skip_next_irrigation(reason: str | None = None) -> dict[str, Any]:
    """Backward-compatible alias used by older Orion code.

    The scheduler now consumes a skip flag internally when it reaches the
    scheduled run time. Calling this directly clears the skip-next flag and
    returns the updated Orion-controlled schedule.
    """
    result = clear_skip_next_irrigation()
    result["action"] = "consume_skip_next_irrigation"
    result["consumed"] = True
    if reason:
        result["reason"] = reason
    return result


def _today_name(now: float | None = None) -> str:
    return VALID_DAYS[time.localtime(now or time.time()).tm_wday]


def _run_key(schedule: dict[str, Any], now: float | None = None) -> str:
    lt = time.localtime(now or time.time())
    return f"{lt.tm_year:04d}-{lt.tm_mon:02d}-{lt.tm_mday:02d}:{schedule.get('start_time', '06:00')}"


def _current_time_string(now: float | None = None) -> str:
    lt = time.localtime(now or time.time())
    return f"{lt.tm_hour:02d}:{lt.tm_min:02d}"


def _rain_likely(weather: dict[str, Any] | None) -> bool:
    try:
        return float((weather or {}).get("rain_chance") or 0) >= 70
    except Exception:
        return False


def _scheduler_event(event_type: str, message: str, **extra: Any) -> dict[str, Any]:
    event = {
        "type": event_type,
        "time": time.time(),
        "message": message,
    }
    event.update(extra)
    return event


def _live_sprinkler_running_from_status() -> tuple[bool | None, dict[str, Any]]:
    """Return live sprinkler running state from the controller.

    The UI/device cache can be a couple seconds old. The scheduler must use a
    fresh status read before advancing zones, otherwise it can think a zone is
    done while the controller is still watering.
    """
    status = get_sprinkler_status()
    if not status.get("ok"):
        return None, status

    response = status.get("response")
    if isinstance(response, dict):
        return _is_sprinkler_running(response), status

    return False, status


def _mark_schedule_event(
    schedule: dict[str, Any],
    event_type: str,
    message: str,
    *,
    now_value: float,
    save: bool = True,
    **extra: Any,
) -> dict[str, Any]:
    schedule["last_scheduler_event"] = _scheduler_event(event_type, message, **extra)
    schedule["updated_at"] = now_value
    normalized = _normalize_schedule(schedule)
    if save:
        _save_schedule_file(normalized)
    return normalized


def _active_run_from_schedule(schedule: dict[str, Any]) -> dict[str, Any] | None:
    active_run = schedule.get("active_run")
    if not isinstance(active_run, dict):
        return None

    pending = active_run.get("pending_zones")
    completed = active_run.get("completed_zones")

    if not isinstance(pending, list):
        active_run["pending_zones"] = []
    if not isinstance(completed, list):
        active_run["completed_zones"] = []

    return active_run


def _start_scheduled_zone(
    *,
    schedule: dict[str, Any],
    current_run: dict[str, Any],
    zone: int,
    pending_zones: list[int],
    completed_zones: list[int],
    now_value: float,
    event_type: str,
) -> dict[str, Any]:
    """Start one scheduled zone and persist runtime only if hardware accepts it."""
    duration = int(schedule.get("duration_minutes") or 10)
    result = run_sprinkler_zone(zone, duration, manual_override=False)

    if not result.get("ok"):
        # Do not mutate current_zone/pending on failed start. This preserves the
        # queue and lets the next scheduler tick retry if appropriate.
        current_run.update(
            {
                "current_zone": None,
                "pending_zones": [zone, *pending_zones],
                "completed_zones": completed_zones,
                "last_result": result,
                "last_error_at": now_value,
            }
        )
        schedule["active_run"] = current_run
        normalized = _mark_schedule_event(
            schedule,
            "zone_start_failed",
            f"Scheduled zone {zone} could not start.",
            now_value=now_value,
            zone=zone,
            result=result,
        )
        return {
            "ok": False,
            "executed": False,
            "event": "zone_start_failed",
            "message": f"Scheduled zone {zone} could not start.",
            "result": result,
            "schedule": normalized,
        }

    current_run.update(
        {
            "current_zone": zone,
            "pending_zones": pending_zones,
            "completed_zones": completed_zones,
            "last_zone_started_at": now_value,
            "last_result": result,
        }
    )
    schedule["active_run"] = current_run
    normalized = _mark_schedule_event(
        schedule,
        event_type,
        f"Started scheduled zone {zone}.",
        now_value=now_value,
        zone=zone,
        result=result,
    )
    return {
        "ok": True,
        "executed": True,
        "event": event_type,
        "message": f"Started scheduled zone {zone}.",
        "result": result,
        "schedule": normalized,
    }



def _time_to_seconds(value: Any) -> int | None:
    try:
        text = _normalize_time(value)
        hour, minute = text.split(":", 1)
        return int(hour) * 3600 + int(minute) * 60
    except Exception:
        return None


def _current_seconds(now: float | None = None) -> int:
    lt = time.localtime(now or time.time())
    return int(lt.tm_hour) * 3600 + int(lt.tm_min) * 60 + int(lt.tm_sec)


def _inside_schedule_window(schedule: dict[str, Any], now: float | None = None) -> bool:
    target = _time_to_seconds(schedule.get("start_time"))
    if target is None:
        return False
    elapsed = _current_seconds(now) - target
    return 0 <= elapsed <= SCHEDULE_START_GRACE_SECONDS


def _expected_zone_done_at(started_at: float, duration_minutes: int) -> float:
    return float(started_at) + (max(MIN_ZONE_MINUTES, int(duration_minutes)) * 60) + ZONE_COMPLETION_BUFFER_SECONDS


def _save_scheduler_schedule(schedule: dict[str, Any], now_value: float) -> dict[str, Any]:
    schedule["updated_at"] = now_value
    normalized = _normalize_schedule(schedule)
    _save_schedule_file(normalized)
    return normalized


def _scheduler_response(
    *,
    ok: bool = True,
    executed: bool = False,
    event: str,
    message: str,
    schedule: dict[str, Any],
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": ok,
        "executed": executed,
        "event": event,
        "message": message,
        "schedule": schedule,
    }
    if result is not None:
        payload["result"] = result
    return payload


def run_orion_scheduler_tick(
    *,
    now: float | None = None,
    weather: dict[str, Any] | None = None,
    sprinkler: dict[str, Any] | None = None,
    automation_mode: str = "manual",
) -> dict[str, Any]:
    """Advance Orion's local irrigation scheduler by one tick.

    Clean scheduler behavior:
    - Orion owns the schedule; no hardware schedule endpoint is called.
    - The sprinkler node is treated as a start/stop actuator.
    - At the scheduled time, Orion starts one zone only.
    - The next zone starts only after the current zone finishes or its expected
      duration has elapsed.
    - Rain can skip a pending run or abort an active scheduled run.
    - A run is processed once per date/start_time key.
    """
    now_value = now or time.time()
    schedule = get_irrigation_schedule()

    if schedule.get("controller") == "sprinkler" and schedule.get("hardware_synced"):
        return _scheduler_response(
            event="sprinkler_controller_active",
            message="Sprinkler controller owns scheduled execution. Orion is monitoring only.",
            schedule=schedule,
        )

    if automation_mode != "auto":
        return _scheduler_response(
            event="manual_mode",
            message="Scheduler idle because automation mode is manual.",
            schedule=schedule,
        )

    if not schedule.get("enabled"):
        return _scheduler_response(
            event="disabled",
            message="Irrigation schedule disabled.",
            schedule=schedule,
        )

    current_run = schedule.get("active_run") if isinstance(schedule.get("active_run"), dict) else None
    sprinkler_data = sprinkler if isinstance(sprinkler, dict) else {}
    sprinkler_running = _is_sprinkler_running(sprinkler_data.get("raw", sprinkler_data)) or bool(sprinkler_data.get("running"))

    # Active queued run: monitor current zone, then move to next zone safely.
    if current_run:
        pending = [int(zone) for zone in (current_run.get("pending_zones") or [])]
        completed = [int(zone) for zone in (current_run.get("completed_zones") or [])]
        current_zone = current_run.get("current_zone")
        duration = int(schedule.get("duration_minutes") or 10)
        last_started = float(current_run.get("last_zone_started_at") or now_value)
        expected_done_at = float(current_run.get("expected_zone_done_at") or _expected_zone_done_at(last_started, duration))
        observed_running = bool(current_run.get("observed_running"))

        # Weather safety can abort a scheduled run in progress.
        if schedule.get("skip_if_rain_likely") and _rain_likely(weather):
            stop_result = stop_sprinkler() if sprinkler_running else None
            schedule["active_run"] = None
            schedule["last_scheduler_event"] = _scheduler_event(
                "run_aborted_weather",
                "Scheduled irrigation aborted because rain is likely.",
                current_zone=current_zone,
                stop_result=stop_result,
            )
            normalized = _save_scheduler_schedule(schedule, now_value)
            return _scheduler_response(
                ok=bool(stop_result.get("ok", True)) if isinstance(stop_result, dict) else True,
                executed=bool(stop_result),
                event="run_aborted_weather",
                message="Scheduled irrigation aborted because rain is likely.",
                result=stop_result,
                schedule=normalized,
            )

        if sprinkler_running:
            if not observed_running:
                current_run["observed_running"] = True
                current_run["last_observed_running_at"] = now_value
                schedule["active_run"] = current_run
                schedule["last_scheduler_event"] = _scheduler_event(
                    "zone_running",
                    f"Scheduled zone {current_zone} is running.",
                    zone=current_zone,
                )
                normalized = _save_scheduler_schedule(schedule, now_value)
            else:
                normalized = schedule

            return _scheduler_response(
                event="zone_running",
                message=f"Scheduled zone {current_zone} is running.",
                schedule=normalized,
            )

        # If hardware has not yet reported running, wait until the expected
        # duration expires before treating the zone as complete. This prevents
        # rapid-fire zone starts when the status endpoint lags or is limited.
        if current_zone is not None and not observed_running and now_value < expected_done_at:
            wait_seconds = max(0.0, expected_done_at - now_value)
            return _scheduler_response(
                event="awaiting_zone_feedback",
                message=f"Waiting for scheduled zone {current_zone} to finish or confirm status ({wait_seconds:.0f}s remaining).",
                schedule=schedule,
            )

        if current_zone is not None and int(current_zone) not in completed:
            completed.append(int(current_zone))

        if pending:
            next_zone = int(pending.pop(0))
            result = run_sprinkler_zone(next_zone, duration, manual_override=False)

            if not result.get("ok"):
                schedule["active_run"] = None
                schedule["last_scheduler_event"] = _scheduler_event(
                    "zone_start_failed",
                    f"Scheduled zone {next_zone} failed to start. Run aborted for safety.",
                    zone=next_zone,
                    result=result,
                    completed_zones=completed,
                    pending_zones=pending,
                )
                normalized = _save_scheduler_schedule(schedule, now_value)
                return _scheduler_response(
                    ok=False,
                    executed=False,
                    event="zone_start_failed",
                    message=f"Scheduled zone {next_zone} failed to start. Run aborted for safety.",
                    result=result,
                    schedule=normalized,
                )

            current_run.update(
                {
                    "current_zone": next_zone,
                    "pending_zones": pending,
                    "completed_zones": completed,
                    "last_zone_started_at": now_value,
                    "expected_zone_done_at": _expected_zone_done_at(now_value, duration),
                    "observed_running": False,
                    "last_result": result,
                }
            )
            schedule["active_run"] = current_run
            schedule["last_scheduler_event"] = _scheduler_event(
                "zone_started",
                f"Started scheduled zone {next_zone}.",
                zone=next_zone,
                result=result,
                completed_zones=completed,
                pending_zones=pending,
            )
            normalized = _save_scheduler_schedule(schedule, now_value)
            return _scheduler_response(
                ok=True,
                executed=True,
                event="zone_started",
                message=f"Started scheduled zone {next_zone}.",
                result=result,
                schedule=normalized,
            )

        schedule["active_run"] = None
        schedule["last_scheduler_event"] = _scheduler_event(
            "run_completed",
            "Scheduled irrigation run completed.",
            completed_zones=completed,
        )
        normalized = _save_scheduler_schedule(schedule, now_value)
        return _scheduler_response(
            event="run_completed",
            message="Scheduled irrigation run completed.",
            schedule=normalized,
        )

    day = _today_name(now_value)
    if day not in set(schedule.get("days") or []):
        return _scheduler_response(
            event="not_scheduled_day",
            message="No irrigation scheduled for today.",
            schedule=schedule,
        )

    if not _inside_schedule_window(schedule, now_value):
        return _scheduler_response(
            event="waiting_for_time",
            message="Waiting for scheduled irrigation time.",
            schedule=schedule,
        )

    key = _run_key(schedule, now_value)
    if schedule.get("last_run_key") == key:
        return _scheduler_response(
            event="already_processed",
            message="Today's scheduled irrigation run was already processed.",
            schedule=schedule,
        )

    # From here on, today's scheduled window is consumed so Orion does not spam
    # starts/retries every loop tick.
    schedule["last_run_key"] = key

    if schedule.get("skip_next_run"):
        message = schedule.get("skip_reason") or "Scheduled run skipped by Orion."
        schedule["skip_next_run"] = False
        schedule["skip_reason"] = None
        schedule["last_scheduler_event"] = _scheduler_event("run_skipped", message)
        normalized = _save_scheduler_schedule(schedule, now_value)
        return _scheduler_response(
            event="run_skipped",
            message=message,
            schedule=normalized,
        )

    if schedule.get("skip_if_rain_likely") and _rain_likely(weather):
        message = "Scheduled run skipped because rain is likely."
        schedule["last_scheduler_event"] = _scheduler_event("run_skipped_weather", message)
        normalized = _save_scheduler_schedule(schedule, now_value)
        return _scheduler_response(
            event="run_skipped_weather",
            message=message,
            schedule=normalized,
        )

    if sprinkler_running:
        message = "Scheduled run was not started because sprinkler is already running."
        schedule["last_scheduler_event"] = _scheduler_event("run_blocked_sprinkler_busy", message)
        normalized = _save_scheduler_schedule(schedule, now_value)
        return _scheduler_response(
            ok=False,
            event="run_blocked_sprinkler_busy",
            message=message,
            schedule=normalized,
        )

    zones = [int(zone) for zone in (schedule.get("zones") or [])]
    if not zones:
        schedule["last_scheduler_event"] = _scheduler_event("no_zones", "No zones configured for schedule.")
        normalized = _save_scheduler_schedule(schedule, now_value)
        return _scheduler_response(
            ok=False,
            event="no_zones",
            message="No zones configured for schedule.",
            schedule=normalized,
        )

    duration = int(schedule.get("duration_minutes") or 10)
    first_zone = int(zones[0])
    pending = [int(zone) for zone in zones[1:]]
    result = run_sprinkler_zone(first_zone, duration, manual_override=False)

    if not result.get("ok"):
        schedule["active_run"] = None
        schedule["last_scheduler_event"] = _scheduler_event(
            "run_start_failed",
            f"Scheduled zone {first_zone} failed to start. Run aborted for safety.",
            zone=first_zone,
            result=result,
            pending_zones=pending,
        )
        normalized = _save_scheduler_schedule(schedule, now_value)
        return _scheduler_response(
            ok=False,
            executed=False,
            event="run_start_failed",
            message=f"Scheduled zone {first_zone} failed to start. Run aborted for safety.",
            result=result,
            schedule=normalized,
        )

    schedule["active_run"] = {
        "run_key": key,
        "started_at": now_value,
        "current_zone": first_zone,
        "pending_zones": pending,
        "completed_zones": [],
        "last_zone_started_at": now_value,
        "expected_zone_done_at": _expected_zone_done_at(now_value, duration),
        "observed_running": False,
        "last_result": result,
    }
    schedule["last_scheduler_event"] = _scheduler_event(
        "run_started",
        f"Started scheduled irrigation at zone {first_zone}.",
        zone=first_zone,
        result=result,
        pending_zones=pending,
    )
    normalized = _save_scheduler_schedule(schedule, now_value)
    return _scheduler_response(
        ok=True,
        executed=True,
        event="run_started",
        message=f"Started scheduled irrigation at zone {first_zone}.",
        result=result,
        schedule=normalized,
    )


def _extract_schedule_time(text: str) -> str | None:
    patterns = [
        r"\b(?:at|time)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b",
        r"\b(\d{1,2}:\d{2}\s*(?:am|pm)?)\b",
        r"\b(\d{1,2}\s*(?:am|pm))\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return _normalize_time(match.group(1))

    if "morning" in text:
        return "06:00"
    if "evening" in text:
        return "18:00"

    return None


def _extract_schedule_days(text: str) -> list[str] | None:
    lowered = text.lower()
    if any(x in lowered for x in ["every day", "everyday", "daily", "all days"]):
        return VALID_DAYS.copy()
    if any(x in lowered for x in ["weekday", "weekdays", "mon-fri"]):
        return ["mon", "tue", "wed", "thu", "fri"]
    if any(x in lowered for x in ["weekend", "weekends", "sat-sun"]):
        return ["sat", "sun"]

    days = []
    for word, normalized in DAY_ALIASES.items():
        if re.search(rf"\b{re.escape(word)}\b", lowered) and normalized not in days:
            days.append(normalized)

    return days or None


def _extract_schedule_payload_from_text(text: str) -> dict[str, Any]:
    lowered = text.lower()
    payload: dict[str, Any] = {}

    if any(x in lowered for x in ["disable schedule", "turn schedule off", "schedule off"]):
        payload["enabled"] = False
    elif any(x in lowered for x in ["enable schedule", "turn schedule on", "schedule on"]):
        payload["enabled"] = True

    schedule_time = _extract_schedule_time(lowered)
    if schedule_time:
        payload["start_time"] = schedule_time

    days = _extract_schedule_days(lowered)
    if days:
        payload["days"] = days

    minutes = _extract_minutes(lowered, default=10)
    if re.search(r"\b(\d+)\s*(?:minute|minutes|min|mins)\b", lowered):
        payload["duration_minutes"] = minutes

    if "all zones" in lowered or "every zone" in lowered:
        payload["zones"] = list(range(1, SPRINKLER_ZONES + 1))
    else:
        zones = []
        for match in re.findall(r"\bzone\s*(\d+)\b", lowered):
            zone = int(match)
            if 1 <= zone <= SPRINKLER_ZONES and zone not in zones:
                zones.append(zone)
        if zones:
            payload["zones"] = zones

    return payload


# -------------------------
# THERMOSTAT CONTROL
# -------------------------
def get_thermostat_status() -> dict[str, Any]:
    return _get_status(
        THERMOSTAT_BASE_URL,
        [
            "/api/hvac/status",
            "/api/status",
            "/status",
            "/api/thermostat/status",
        ],
    )


def set_thermostat_setpoint(temp: int) -> dict[str, Any]:
    temp = int(temp)

    if temp < MIN_SETPOINT or temp > MAX_SETPOINT:
        return {
            "ok": False,
            "error": f"Invalid setpoint. Allowed range is {MIN_SETPOINT}-{MAX_SETPOINT}°F.",
        }

    return _post_candidates(
        THERMOSTAT_BASE_URL,
        [
            ("/api/hvac/setpoint", {"setpoint": temp}),
            ("/api/hvac/setpoint", {"temp": temp}),
            ("/api/hvac/set_temp", {"temp": temp}),
            ("/api/hvac/temp", {"temp": temp}),
            ("/api/setpoint", {"setpoint": temp}),
            ("/api/set_temp", {"temp": temp}),
            ("/setpoint", {"setpoint": temp}),
        ],
        timeout=8.0,
    )


def set_thermostat_mode(mode: str) -> dict[str, Any]:
    mode = mode.lower().strip()

    if mode not in VALID_HVAC_MODES:
        return {
            "ok": False,
            "error": f"Invalid HVAC mode. Allowed modes: {sorted(VALID_HVAC_MODES)}",
        }

    return _post_candidates(
        THERMOSTAT_BASE_URL,
        [
            ("/api/hvac/mode", {"mode": mode}),
            ("/api/mode", {"mode": mode}),
            ("/mode", {"mode": mode}),
        ],
        timeout=8.0,
    )


def set_thermostat_fan(mode: str) -> dict[str, Any]:
    mode = mode.lower().strip()

    if mode not in VALID_FAN_MODES:
        return {
            "ok": False,
            "error": f"Invalid fan mode. Allowed modes: {sorted(VALID_FAN_MODES)}",
        }

    return _post_candidates(
        THERMOSTAT_BASE_URL,
        [
            ("/api/hvac/fan", {"fan": mode}),
            ("/api/hvac/fan", {"mode": mode}),
            ("/api/fan", {"fan": mode}),
            ("/fan", {"fan": mode}),
        ],
        timeout=8.0,
    )


# -------------------------
# NATURAL LANGUAGE COMMAND HANDLER
# -------------------------
def handle_device_command(prompt: str | None) -> dict[str, Any]:
    text = (prompt or "").strip()
    lowered = text.lower()

    if not lowered:
        return {
            "ok": False,
            "error": "No command provided.",
        }

    # -------------------------
    # SPRINKLER COMMANDS
    # -------------------------
    if any(word in lowered for word in ["sprinkler", "water", "watering", "zone", "irrigation", "schedule"]):
        if any(phrase in lowered for phrase in ["skip next", "skip watering", "delay irrigation", "delay watering", "skip irrigation"]):
            return skip_next_irrigation("Requested from Orion chat")

        if "schedule" in lowered or "every day" in lowered or "everyday" in lowered or "weekday" in lowered or "weekend" in lowered:
            payload = _extract_schedule_payload_from_text(lowered)
            return set_irrigation_schedule(**payload)

        zone = _extract_zone(lowered)

        if zone is not None and any(
            word in lowered for word in ["stop", "off", "cancel"]
        ):
            return stop_sprinkler_zone(zone)

        if any(
            phrase in lowered
            for phrase in ["stop sprinkler", "stop all", "force off", "all off"]
        ):
            return stop_sprinkler()

        if any(
            phrase in lowered
            for phrase in ["program", "run cycle", "run today", "today's program"]
        ):
            return run_sprinkler_program_now()

        minutes = _extract_minutes(lowered, default=1)

        if zone is not None and any(
            word in lowered for word in ["run", "start", "water", "on", "turn on"]
        ):
            return run_sprinkler_zone(zone=zone, minutes=minutes)

        return {
            "ok": False,
            "error": "Sprinkler command not understood. Try: 'run sprinkler zone 3 for 2 minutes', 'stop zone 3', 'stop sprinkler', or 'run cycle'.",
        }

    # -------------------------
    # THERMOSTAT COMMANDS
    # -------------------------
    if any(
        word in lowered
        for word in [
            "thermostat",
            "hvac",
            "cool",
            "heat",
            "fan",
            "temperature",
            "setpoint",
        ]
    ):
        fan_mode = _extract_fan_mode(lowered)
        if fan_mode:
            return set_thermostat_fan(fan_mode)

        hvac_mode = _extract_hvac_mode(lowered)
        if hvac_mode and any(
            word in lowered for word in ["mode", "cool", "heat", "auto", "off"]
        ):
            return set_thermostat_mode(hvac_mode)

        setpoint = _extract_setpoint(lowered)
        if setpoint is not None:
            return set_thermostat_setpoint(setpoint)

        return {
            "ok": False,
            "error": "Thermostat command not understood. Try: 'set thermostat to 72', 'set mode cool', or 'fan on'.",
        }

    return {
        "ok": False,
        "error": "No device command detected.",
    }


def describe_control_capabilities() -> str:
    return (
        "Device control is available.\n\n"
        "Sprinkler commands:\n"
        "- run sprinkler zone 3 for 2 minutes\n"
        "- stop zone 3\n"
        "- stop sprinkler\n"
        "- run cycle\n"
        "- skip next irrigation\n"
        "- set sprinkler schedule weekdays at 6am for 10 minutes all zones\n\n"
        "Thermostat commands:\n"
        "- set thermostat to 72\n"
        "- set mode cool\n"
        "- set mode heat\n"
        "- set mode auto\n"
        "- turn fan on\n"
        "- turn fan off"
    )