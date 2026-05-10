import os
import time
from threading import Lock
from typing import Any
from urllib.parse import quote

import requests


WEATHER_LOCATION = os.getenv("WEATHER_LOCATION", "auto").strip()
WEATHER_CACHE_SECONDS = int(os.getenv("WEATHER_CACHE_SECONDS", "600"))

_weather_lock = Lock()
_weather_cache: dict[str, Any] | None = None
_weather_cache_time = 0.0


def _safe_float(value):
    try:
        return float(value)
    except Exception:
        return None


def _safe_int(value):
    try:
        return int(float(value))
    except Exception:
        return None


def _build_weather_url():
    if not WEATHER_LOCATION or WEATHER_LOCATION.lower() == "auto":
        return "https://wttr.in/?format=j1"

    return f"https://wttr.in/{quote(WEATHER_LOCATION)}?format=j1"


def _extract_location(data: dict[str, Any]):
    try:
        nearest = data.get("nearest_area", [])
        if not nearest:
            return WEATHER_LOCATION if WEATHER_LOCATION != "auto" else "auto"

        area = nearest[0]

        area_name = ""
        region = ""
        country = ""

        if area.get("areaName"):
            area_name = area["areaName"][0].get("value", "")

        if area.get("region"):
            region = area["region"][0].get("value", "")

        if area.get("country"):
            country = area["country"][0].get("value", "")

        parts = [x for x in [area_name, region, country] if x]
        return ", ".join(parts) if parts else WEATHER_LOCATION

    except Exception:
        return WEATHER_LOCATION if WEATHER_LOCATION else "auto"


def _extract_condition(current: dict[str, Any]):
    try:
        desc = current.get("weatherDesc", [])
        if desc:
            return desc[0].get("value", "unknown")
    except Exception:
        pass

    return "unknown"


def _extract_rain_chance(data: dict[str, Any]):
    chances = []

    try:
        for day in data.get("weather", [])[:2]:
            for hourly in day.get("hourly", []):
                chance = _safe_int(hourly.get("chanceofrain"))
                if chance is not None:
                    chances.append(chance)
    except Exception:
        pass

    if not chances:
        return None

    return max(chances)


def _extract_today_forecast(data: dict[str, Any]):
    try:
        days = data.get("weather", [])
        if not days:
            return None

        today = days[0]
        astronomy = today.get("astronomy", [])

        return {
            "date": today.get("date"),
            "max_temp": _safe_float(today.get("maxtempF")),
            "min_temp": _safe_float(today.get("mintempF")),
            "sunrise": astronomy[0].get("sunrise") if astronomy else None,
            "sunset": astronomy[0].get("sunset") if astronomy else None,
        }

    except Exception:
        return None


def _offline_weather(error: str):
    return {
        "online": False,
        "location": WEATHER_LOCATION if WEATHER_LOCATION else "auto",
        "temp": None,
        "feels_like": None,
        "humidity": None,
        "condition": "unknown",
        "rain_chance": None,
        "wind_mph": None,
        "precip_in": None,
        "forecast_today": None,
        "source": _build_weather_url(),
        "updated_at": None,
        "cache_age_seconds": None,
        "error": error,
    }


def _fetch_weather():
    url = _build_weather_url()

    response = requests.get(
        url,
        timeout=5,
        headers={
            "User-Agent": "OrionV2/1.0",
        },
    )
    response.raise_for_status()

    data = response.json()
    current_list = data.get("current_condition", [])

    if not current_list:
        raise ValueError("Weather response missing current_condition")

    current = current_list[0]
    now = time.time()

    return {
        "online": True,
        "location": _extract_location(data),
        "temp": _safe_float(current.get("temp_F")),
        "feels_like": _safe_float(current.get("FeelsLikeF")),
        "humidity": _safe_float(current.get("humidity")),
        "condition": _extract_condition(current),
        "rain_chance": _extract_rain_chance(data),
        "wind_mph": _safe_float(current.get("windspeedMiles")),
        "precip_in": _safe_float(current.get("precipInches")),
        "forecast_today": _extract_today_forecast(data),
        "source": url,
        "updated_at": now,
        "cache_age_seconds": 0,
        "error": None,
    }


def get_weather(force=False):
    global _weather_cache
    global _weather_cache_time

    now = time.time()

    with _weather_lock:
        if (
            not force
            and _weather_cache is not None
            and now - _weather_cache_time < WEATHER_CACHE_SECONDS
        ):
            cached = dict(_weather_cache)
            cached["cache_age_seconds"] = int(now - _weather_cache_time)
            return cached

    try:
        weather = _fetch_weather()

        with _weather_lock:
            _weather_cache = dict(weather)
            _weather_cache_time = time.time()

        return weather

    except Exception as e:
        offline = _offline_weather(str(e))

        with _weather_lock:
            if _weather_cache is not None:
                cached = dict(_weather_cache)
                cached["online"] = False
                cached["error"] = str(e)
                cached["cache_age_seconds"] = int(now - _weather_cache_time)
                return cached

            # Cache offline result too, so the loop does not retry every 0.25s.
            _weather_cache = dict(offline)
            _weather_cache_time = time.time()

        return offline