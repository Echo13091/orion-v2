import os
from typing import Any

import requests


SPRINKLER_BASE_URL = os.getenv(
    "SPRINKLER_BASE_URL",
    "http://192.168.7.232:5000",
).rstrip("/")

THERMOSTAT_BASE_URL = os.getenv(
    "THERMOSTAT_BASE_URL",
    "http://192.168.7.232:5002",
).rstrip("/")

SPRINKLER_ZONES = int(os.getenv("SPRINKLER_ZONES", "8"))
DEVICE_HTTP_TIMEOUT = float(os.getenv("ORION_DEVICE_HTTP_TIMEOUT", "4.0"))


def _get_json_from_candidates(
    base_url: str,
    paths: list[str],
    timeout: float = DEVICE_HTTP_TIMEOUT,
):
    errors = []

    for path in paths:
        url = f"{base_url}{path}"

        try:
            response = requests.get(
                url,
                timeout=timeout,
                headers={"Accept": "application/json"},
            )

            if not (200 <= response.status_code < 300):
                errors.append(
                    f"{url} -> HTTP {response.status_code}: {response.text[:160]}"
                )
                continue

            try:
                data = response.json()
            except Exception as exc:
                errors.append(f"{url} -> non-JSON response: {exc}")
                continue

            if not isinstance(data, dict):
                errors.append(f"{url} -> JSON response was not an object")
                continue

            return data, url, None

        except requests.exceptions.Timeout:
            errors.append(f"{url} -> timeout after {timeout:.1f}s")

        except requests.exceptions.ConnectionError as exc:
            errors.append(f"{url} -> connection error: {exc}")

        except Exception as exc:
            errors.append(f"{url} -> {exc}")

    return None, None, " | ".join(errors) if errors else "No endpoint responded"


def _first_present(data: dict[str, Any], keys: list[str], default=None):
    for key in keys:
        if key in data:
            value = data.get(key)

            if value is not None and value != "":
                return value

    return default


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value

    if value is None:
        return default

    if isinstance(value, (int, float)):
        return value != 0

    text = str(value).strip().lower()

    if text in {
        "1",
        "true",
        "yes",
        "on",
        "online",
        "ok",
        "active",
        "running",
        "alive",
    }:
        return True

    if text in {
        "0",
        "false",
        "no",
        "off",
        "offline",
        "bad",
        "fault",
        "none",
        "dead",
        "down",
    }:
        return False

    return default


def _as_int(value: Any):
    try:
        return int(float(value))
    except Exception:
        return None


def _human_zone(value: Any):
    zone = _as_int(value)

    if zone is None:
        return value

    if 1 <= zone <= SPRINKLER_ZONES:
        return zone

    if zone == 0:
        return 1

    return zone


def _zero_based_index_to_zone(value: Any):
    zone_index = _as_int(value)

    if zone_index is None:
        return value

    zone = zone_index + 1

    if 1 <= zone <= SPRINKLER_ZONES:
        return zone

    return value


def _extract_active_zone(data: dict[str, Any]):
    direct = _first_present(
        data,
        [
            "zone",
            "current_zone",
            "active_zone",
        ],
    )

    if direct is not None:
        return _human_zone(direct)

    index = _first_present(
        data,
        [
            "zone_index",
            "current_zone_index",
            "active_zone_index",
        ],
    )

    if index is not None:
        return _zero_based_index_to_zone(index)

    zones = data.get("zones")

    if isinstance(zones, list):
        for i, active in enumerate(zones):
            if _as_bool(active):
                return i + 1

    active_zones = data.get("active_zones")

    if isinstance(active_zones, list) and active_zones:
        return _human_zone(active_zones[0])

    return None


def _extract_timeline(data: dict[str, Any]) -> list[dict[str, Any]]:
    for key in (
        "upcoming_zone_timeline",
        "upcoming_timeline",
        "upcoming_zones",
        "timeline",
        "computed_schedule",
        "schedule",
    ):
        value = data.get(key)

        if isinstance(value, list) and value:
            return value

    return []


def _extract_next_run(data: dict[str, Any]):
    if data.get("next_run"):
        return data.get("next_run")

    program = data.get("program")

    if isinstance(program, dict):
        start_time = program.get("start_time")

        if start_time:
            return {
                "time": start_time,
                "days": program.get("days"),
                "durations": program.get("durations"),
            }

    return None


def _sprinkler_running(data: dict[str, Any]) -> bool:
    if _as_bool(
        _first_present(
            data,
            [
                "running",
                "is_running",
                "active",
                "cycle_running",
            ],
        )
    ):
        return True

    zones = data.get("zones")

    if isinstance(zones, list) and any(_as_bool(v) for v in zones):
        return True

    return False


def get_sprinkler_state():
    data, source_url, error = _get_json_from_candidates(
        SPRINKLER_BASE_URL,
        [
            "/api/status",
            "/status",
            "/api/sprinkler/status",
        ],
    )

    if data is None:
        return {
            "online": False,
            "node_online": False,
            "service_online": False,
            "backend_online": False,
            "source": None,
            "running": False,
            "zone": None,
            "active_zone": None,
            "current_zone": None,
            "current_zone_index": None,
            "mode": "offline",
            "health": "offline",
            "heartbeat": "offline",
            "fault": True,
            "fault_code": "SPRINKLER_OFFLINE",
            "fault_message": error or "Sprinkler controller offline",
            "fault_severity": "critical",
            "alarms": [],
            "next_run": None,
            "next_zone": None,
            "remaining": None,
            "remaining_seconds": None,
            "zones": [],
            "relay_zones": [],
            "zone_count": SPRINKLER_ZONES,
            "timeline": [],
            "upcoming_timeline": [],
            "upcoming_zone_timeline": [],
            "upcoming_zones": [],
            "program": None,
            "schedule": None,
            "error": error,
            "raw": None,
        }

    online = _as_bool(data.get("online"), True)
    node_online = _as_bool(data.get("node_online"), online)
    service_online = _as_bool(data.get("service_online"), True)
    backend_online = _as_bool(data.get("backend_online"), service_online)

    running = _sprinkler_running(data)
    active_zone = _extract_active_zone(data)
    timeline = _extract_timeline(data)

    fault = (
        _as_bool(data.get("fault"), False)
        or not online
        or not node_online
    )

    health = (
        data.get("health")
        or ("online" if online and node_online else "offline")
    )

    return {
        "online": bool(online and node_online),
        "node_online": node_online,
        "service_online": service_online,
        "backend_online": backend_online,
        "source": source_url,
        "running": running,
        "zone": active_zone,
        "active_zone": active_zone,
        "current_zone": active_zone,
        "current_zone_index": data.get("current_zone_index"),
        "mode": data.get("mode") or data.get("state") or ("running" if running else "idle"),
        "health": health,
        "heartbeat": data.get("heartbeat") or ("online" if node_online else "offline"),
        "fault": fault,
        "fault_code": data.get("fault_code") or ("SPRINKLER_OFFLINE" if fault else ""),
        "fault_message": data.get("fault_message") or ("Sprinkler node offline" if fault else ""),
        "fault_severity": data.get("fault_severity") or ("critical" if fault else ""),
        "alarms": data.get("alarms") if isinstance(data.get("alarms"), list) else [],
        "next_run": _extract_next_run(data),
        "next_zone": data.get("next_zone"),
        "remaining": data.get("remaining") or data.get("remaining_seconds"),
        "remaining_seconds": data.get("remaining_seconds") or data.get("remaining"),
        "zones": data.get("zones") if isinstance(data.get("zones"), list) else [],
        "relay_zones": data.get("relay_zones") if isinstance(data.get("relay_zones"), list) else [],
        "zone_count": data.get("zone_count") or SPRINKLER_ZONES,
        "timeline": timeline,
        "upcoming_timeline": timeline,
        "upcoming_zone_timeline": timeline,
        "upcoming_zones": timeline,
        "program": data.get("program"),
        "schedule": data.get("schedule"),
        "error": None,
        "raw": data,
    }


def get_thermostat_state():
    data, source_url, error = _get_json_from_candidates(
        THERMOSTAT_BASE_URL,
        [
            "/api/hvac/status",
            "/api/status",
            "/status",
            "/api/thermostat/status",
        ],
    )

    if data is None:
        return {
            "online": False,
            "node_online": False,
            "heartbeat": "offline",
            "source": None,
            "temp": None,
            "temperature": None,
            "current_temp": None,
            "humidity": None,
            "mode": "offline",
            "system_mode": "offline",
            "hvac_mode": "offline",
            "hvac_state": "OFFLINE",
            "health": "offline",
            "cooling": False,
            "heating": False,
            "fan": False,
            "fan_on": False,
            "cooling_active": False,
            "heating_active": False,
            "fan_active": False,
            "relay_cool": False,
            "relay_heat": False,
            "relay_fan": False,
            "relay_cool_stage1": False,
            "relay_cool_stage2": False,
            "relay_heat_stage1": False,
            "relay_heat_stage2": False,
            "cool_stage": 0,
            "heat_stage": 0,
            "cool_stage1": False,
            "cool_stage2": False,
            "heat_stage1": False,
            "heat_stage2": False,
            "setpoint": None,
            "fan_mode": None,
            "stage2_available": False,
            "stage2_enabled": False,
            "sensor_status": "unknown",
            "fault": True,
            "fault_code": "THERMOSTAT_OFFLINE",
            "fault_message": error or "Thermostat controller offline",
            "fault_severity": "critical",
            "alarms": [],
            "last_action": None,
            "error": error,
            "raw": None,
        }

    online = _as_bool(data.get("online"), True)
    node_online = _as_bool(data.get("node_online"), online)

    fault = (
        _as_bool(data.get("fault"), False)
        or not online
        or not node_online
    )

    temp = _first_present(
        data,
        [
            "temp",
            "temperature",
            "current_temp",
            "room_temp",
        ],
    )

    if fault and not online:
        temp = None

    mode = _first_present(
        data,
        [
            "mode",
            "system_mode",
            "hvac_mode",
        ],
        default="auto",
    )

    cooling = _as_bool(
        _first_present(
            data,
            [
                "cooling",
                "cool",
                "cool_call",
                "cooling_active",
                "relay_cool",
            ],
        )
    )

    heating = _as_bool(
        _first_present(
            data,
            [
                "heating",
                "heat",
                "heat_call",
                "heating_active",
                "relay_heat",
            ],
        )
    )

    fan = _as_bool(
        _first_present(
            data,
            [
                "fan",
                "fan_on",
                "fan_active",
                "relay_fan",
            ],
        )
    )

    hvac_state = data.get("hvac_state")

    if not hvac_state:
        if cooling:
            hvac_state = "COOLING"
        elif heating:
            hvac_state = "HEATING"
        elif fan:
            hvac_state = "FAN"
        else:
            hvac_state = "IDLE"

    return {
        "online": bool(online and node_online),
        "node_online": node_online,
        "heartbeat": data.get("heartbeat") or ("online" if node_online else "offline"),
        "source": source_url,
        "temp": temp,
        "temperature": temp,
        "current_temp": temp,
        "humidity": data.get("humidity"),
        "mode": mode,
        "system_mode": data.get("system_mode") or mode,
        "hvac_mode": data.get("hvac_mode") or mode,
        "hvac_state": hvac_state,
        "health": data.get("health") or ("online" if online and node_online else "offline"),
        "cooling": cooling,
        "heating": heating,
        "fan": fan,
        "fan_on": _as_bool(data.get("fan_on"), fan),
        "cooling_active": _as_bool(data.get("cooling_active"), cooling),
        "heating_active": _as_bool(data.get("heating_active"), heating),
        "fan_active": _as_bool(data.get("fan_active"), fan),
        "relay_cool": _as_bool(data.get("relay_cool"), cooling),
        "relay_heat": _as_bool(data.get("relay_heat"), heating),
        "relay_fan": _as_bool(data.get("relay_fan"), fan),
        "relay_cool_stage1": _as_bool(data.get("relay_cool_stage1")),
        "relay_cool_stage2": _as_bool(data.get("relay_cool_stage2")),
        "relay_heat_stage1": _as_bool(data.get("relay_heat_stage1")),
        "relay_heat_stage2": _as_bool(data.get("relay_heat_stage2")),
        "cool_stage": data.get("cool_stage") or 0,
        "heat_stage": data.get("heat_stage") or 0,
        "cool_stage1": _as_bool(data.get("cool_stage1")),
        "cool_stage2": _as_bool(data.get("cool_stage2")),
        "heat_stage1": _as_bool(data.get("heat_stage1")),
        "heat_stage2": _as_bool(data.get("heat_stage2")),
        "setpoint": data.get("setpoint"),
        "fan_mode": data.get("fan_mode"),
        "stage2_available": _as_bool(data.get("stage2_available")),
        "stage2_enabled": _as_bool(data.get("stage2_enabled")),
        "sensor_status": data.get("sensor_status") or "unknown",
        "fault": fault,
        "fault_code": data.get("fault_code") or ("THERMOSTAT_OFFLINE" if fault else ""),
        "fault_message": data.get("fault_message") or ("Thermostat node offline" if fault else ""),
        "fault_severity": data.get("fault_severity") or ("critical" if fault else ""),
        "alarms": data.get("alarms") if isinstance(data.get("alarms"), list) else [],
        "last_action": data.get("last_action"),
        "error": None,
        "raw": data,
    }
