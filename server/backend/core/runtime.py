import os
import subprocess
import time
from datetime import datetime, timedelta
from typing import Any

import psutil

from core.devices import get_sprinkler_state, get_thermostat_state
from core.state import get_state_snapshot, update_state
from tools.weather import get_weather


ENABLE_GPU_METRICS = os.getenv("ORION_ENABLE_GPU_METRICS", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

GPU_SAMPLE_SECONDS = float(os.getenv("ORION_GPU_SAMPLE_SECONDS", "15"))
DEVICE_SAMPLE_SECONDS = float(os.getenv("ORION_DEVICE_SAMPLE_SECONDS", "2.5"))
WEATHER_SAMPLE_SECONDS = float(os.getenv("ORION_WEATHER_SAMPLE_SECONDS", "600"))

_last_gpu_time = 0.0
_last_gpu_value = 0.0

_last_device_time = 0.0
_last_sprinkler: dict[str, Any] | None = None
_last_thermostat: dict[str, Any] | None = None

_last_weather_time = 0.0
_last_weather: dict[str, Any] | None = None

DAY_ORDER = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def get_gpu_usage():
    global _last_gpu_time
    global _last_gpu_value

    if not ENABLE_GPU_METRICS:
        return 0.0

    now = time.time()

    if now - _last_gpu_time < GPU_SAMPLE_SECONDS:
        return _last_gpu_value

    try:
        result = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            stderr=subprocess.DEVNULL,
            timeout=2,
        )

        value = result.decode().strip()

        if "\n" in value:
            value = value.split("\n")[0]

        _last_gpu_value = float(value)

    except Exception:
        _last_gpu_value = 0.0

    _last_gpu_time = now

    return _last_gpu_value


def _sample_devices():
    global _last_device_time
    global _last_sprinkler
    global _last_thermostat

    now = time.time()

    if (
        _last_sprinkler is not None
        and _last_thermostat is not None
        and now - _last_device_time < DEVICE_SAMPLE_SECONDS
    ):
        return dict(_last_sprinkler), dict(_last_thermostat)

    sprinkler = get_sprinkler_state()
    thermostat = get_thermostat_state()

    _last_sprinkler = dict(sprinkler)
    _last_thermostat = dict(thermostat)
    _last_device_time = now

    return sprinkler, thermostat


def _sample_weather():
    global _last_weather_time
    global _last_weather

    now = time.time()

    if _last_weather is not None and now - _last_weather_time < WEATHER_SAMPLE_SECONDS:
        cached = dict(_last_weather)

        if cached.get("updated_at"):
            try:
                cached["cache_age_seconds"] = int(now - float(cached["updated_at"]))
            except Exception:
                pass

        return cached

    try:
        weather = get_weather()

        if not isinstance(weather, dict):
            raise ValueError("weather response was not a dictionary")

    except Exception as exc:
        weather = {
            "online": False,
            "location": None,
            "temp": None,
            "feels_like": None,
            "humidity": None,
            "condition": "unknown",
            "rain_chance": None,
            "wind_mph": None,
            "precip_in": None,
            "forecast_today": None,
            "source": None,
            "updated_at": now,
            "cache_age_seconds": 0,
            "error": str(exc),
        }

    _last_weather = dict(weather)
    _last_weather_time = now

    return weather


def _parse_time(value):
    text = str(value or "").strip()

    if not text:
        return None

    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            pass

    return None


def _format_ampm(dt):
    return dt.strftime("%I:%M %p").lstrip("0")


def _schedule_days(schedule):
    days = schedule.get("days")

    if not isinstance(days, list):
        return []

    aliases = {
        "monday": "mon",
        "mon": "mon",
        "tuesday": "tue",
        "tue": "tue",
        "wednesday": "wed",
        "wed": "wed",
        "thursday": "thu",
        "thu": "thu",
        "friday": "fri",
        "fri": "fri",
        "saturday": "sat",
        "sat": "sat",
        "sunday": "sun",
        "sun": "sun",
        "weekend": "weekend",
        "weekends": "weekend",
    }

    clean = []

    for day in days:
        key = aliases.get(str(day).strip().lower())

        if key == "weekend":
            for weekend_day in ("sat", "sun"):
                if weekend_day not in clean:
                    clean.append(weekend_day)

        elif key and key not in clean:
            clean.append(key)

    return clean


def _schedule_zones(schedule):
    zones = schedule.get("zones")

    if not isinstance(zones, list):
        return []

    clean = []

    for zone in zones:
        try:
            zone_int = int(zone)
        except Exception:
            continue

        if 1 <= zone_int <= 99:
            clean.append(zone_int)

    return clean


def _find_next_schedule_start(schedule):
    if not isinstance(schedule, dict):
        return None

    if not schedule.get("enabled", True):
        return None

    time_part = _parse_time(schedule.get("start_time") or schedule.get("time"))

    if time_part is None:
        return None

    days = _schedule_days(schedule)

    if not days:
        return None

    now = datetime.now()
    candidates = []

    for offset in range(8):
        candidate_day = now + timedelta(days=offset)
        day_key = DAY_ORDER[candidate_day.weekday()]

        if day_key not in days:
            continue

        candidate_dt = datetime.combine(candidate_day.date(), time_part)

        if candidate_dt >= now:
            candidates.append((candidate_dt, day_key))

    if not candidates:
        return None

    return sorted(candidates, key=lambda item: item[0])[0]


def _build_irrigation_timeline(schedule, max_items=16):
    if not isinstance(schedule, dict):
        return []

    next_start = _find_next_schedule_start(schedule)

    if next_start is None:
        return []

    start_dt, day_key = next_start
    zones = _schedule_zones(schedule)

    if not zones:
        return []

    try:
        duration_minutes = int(schedule.get("duration_minutes") or schedule.get("minutes") or 1)
    except Exception:
        duration_minutes = 1

    duration_minutes = max(1, duration_minutes)
    duration_seconds = duration_minutes * 60

    timeline = []
    cursor = start_dt

    for index, zone in enumerate(zones[:max_items]):
        zone_start = cursor
        zone_end = zone_start + timedelta(minutes=duration_minutes)

        timeline.append(
            {
                "index": index,
                "status": "next" if index == 0 else "queued",
                "day": day_key,
                "date": zone_start.strftime("%Y-%m-%d"),
                "zone": zone,
                "zone_index": zone - 1,
                "duration": duration_minutes,
                "duration_minutes": duration_minutes,
                "duration_seconds": duration_seconds,
                "time": zone_start.strftime("%H:%M"),
                "start_time": zone_start.strftime("%H:%M:%S"),
                "end_time": zone_end.strftime("%H:%M:%S"),
                "start_label": _format_ampm(zone_start),
                "end_label": _format_ampm(zone_end),
                "label": f"Zone {zone}",
                "subtitle": f"{duration_minutes} min · ends {_format_ampm(zone_end)}",
                "progress": 0,
            }
        )

        cursor = zone_end

    return timeline


def _attach_irrigation_timeline(sprinkler):
    snapshot = get_state_snapshot()
    schedule = snapshot.get("irrigation_schedule")

    if not isinstance(schedule, dict):
        return sprinkler, None

    schedule = dict(schedule)
    timeline = _build_irrigation_timeline(schedule)

    if not timeline:
        return sprinkler, schedule

    schedule["timeline"] = timeline
    schedule["upcoming_timeline"] = timeline
    schedule["upcoming_zone_timeline"] = timeline
    schedule["upcoming_zones"] = timeline

    sprinkler = dict(sprinkler)
    sprinkler["timeline"] = timeline
    sprinkler["upcoming_timeline"] = timeline
    sprinkler["upcoming_zone_timeline"] = timeline
    sprinkler["upcoming_zones"] = timeline

    if not sprinkler.get("running"):
        first = timeline[0]
        sprinkler["next_run"] = f"{first.get('start_label')} · {first.get('duration_minutes')} min"
        sprinkler["next_zone"] = first.get("zone")

    return sprinkler, schedule


def update_system_metrics():
    cpu = psutil.cpu_percent(interval=0.0)
    memory = psutil.virtual_memory().percent
    gpu = get_gpu_usage()

    sprinkler, thermostat = _sample_devices()
    weather = _sample_weather()

    sprinkler, irrigation_schedule = _attach_irrigation_timeline(sprinkler)

    payload = {
        "cpu": cpu,
        "memory": memory,
        "gpu": gpu,
        "sprinkler": sprinkler,
        "thermostat": thermostat,
        "weather": weather,
    }

    if irrigation_schedule is not None:
        payload["irrigation_schedule"] = irrigation_schedule

    update_state(**payload)