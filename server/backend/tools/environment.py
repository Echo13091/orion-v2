from __future__ import annotations

from typing import Any, Dict, Optional


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def normalize_grass_score(score: float | int | None) -> float:
    try:
        return clamp(float(score) / 100.0, 0.0, 1.0)
    except Exception:
        return 0.5


def normalize_rain_probability(prob: float | int | None) -> float:
    try:
        return clamp(float(prob) / 100.0, 0.0, 1.0)
    except Exception:
        return 0.0


def normalize_dryness(dryness: float | int | None) -> float:
    try:
        return clamp(float(dryness), 0.0, 1.0)
    except Exception:
        return 0.5


def safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        n = float(value)
        return n
    except Exception:
        return default


def is_record(value: Any) -> bool:
    return isinstance(value, dict)


def first_present(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def extract_next_irrigation(sprinkler: Dict[str, Any]) -> Any:
    raw = sprinkler.get("raw") if is_record(sprinkler.get("raw")) else {}

    next_run = first_present(
        sprinkler.get("next_run"),
        raw.get("next_run"),
        raw.get("next_scheduled_run"),
    )

    if next_run:
        return next_run

    # Try timeline-style structures.
    for key in [
        "timeline",
        "upcoming_timeline",
        "upcoming_zone_timeline",
        "upcoming_zones",
    ]:
        items = raw.get(key)
        if isinstance(items, list) and items:
            return items[0]

    return None


def extract_last_irrigation(sprinkler: Dict[str, Any]) -> Any:
    raw = sprinkler.get("raw") if is_record(sprinkler.get("raw")) else {}

    return first_present(
        sprinkler.get("last_run"),
        sprinkler.get("last_irrigation"),
        sprinkler.get("last_scheduler_event"),
        raw.get("last_run"),
        raw.get("last_irrigation"),
        raw.get("last_scheduler_event"),
        raw.get("last_completed_run"),
    )


def summarize_irrigation_context(sprinkler: Dict[str, Any]) -> Dict[str, Any]:
    raw = sprinkler.get("raw") if is_record(sprinkler.get("raw")) else {}

    running = bool(
        sprinkler.get("running")
        or raw.get("running")
        or raw.get("active")
    )

    online = sprinkler.get("online")
    if online is None:
        online = raw.get("online")
    if online is None:
        online = raw.get("service_online")
    if online is None:
        online = True

    zone = first_present(
        sprinkler.get("zone"),
        raw.get("zone"),
        raw.get("active_zone"),
        raw.get("current_zone"),
    )

    next_irrigation = extract_next_irrigation(sprinkler)
    last_irrigation = extract_last_irrigation(sprinkler)

    return {
        "online": bool(online),
        "running": running,
        "zone": zone,
        "next_irrigation": next_irrigation,
        "last_irrigation": last_irrigation,
    }


def classify_lawn_need(
    *,
    grass_score: float,
    dryness_index: float,
    rain_probability: float,
    temp_f: Optional[float],
    humidity: Optional[float],
) -> Dict[str, Any]:
    heat_stress = bool(temp_f is not None and temp_f >= 88)
    extreme_heat = bool(temp_f is not None and temp_f >= 94)
    low_humidity = bool(humidity is not None and humidity <= 40)

    # Higher means more irrigation pressure.
    need_score = 0.0

    # Grass score: lower score means higher need.
    need_score += (1.0 - grass_score) * 0.42

    # Dryness index: direct pressure.
    need_score += dryness_index * 0.32

    # Heat raises need.
    if heat_stress:
        need_score += 0.12
    if extreme_heat:
        need_score += 0.08

    # Low humidity adds stress.
    if low_humidity:
        need_score += 0.06

    # Rain reduces need.
    need_score -= rain_probability * 0.45

    need_score = clamp(need_score, 0.0, 1.0)

    if need_score >= 0.7:
        need_level = "high"
    elif need_score >= 0.45:
        need_level = "moderate"
    elif need_score >= 0.25:
        need_level = "low"
    else:
        need_level = "minimal"

    return {
        "need_score": round(need_score, 3),
        "need_level": need_level,
        "heat_stress": heat_stress,
        "extreme_heat": extreme_heat,
        "low_humidity": low_humidity,
    }


def evaluate_environment(
    *,
    grass_condition: Dict[str, Any] | None,
    weather: Dict[str, Any] | None,
    sprinkler: Dict[str, Any] | None = None,
    rain_detection: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    grass_condition = grass_condition or {}
    weather = weather or {}
    sprinkler = sprinkler or {}
    rain_detection = rain_detection or {}

    grass_score = normalize_grass_score(grass_condition.get("score"))
    dryness_index = normalize_dryness(grass_condition.get("dryness_index"))
    rain_probability = normalize_rain_probability(weather.get("rain_chance"))

    temp_f = safe_float(weather.get("temp"))
    feels_like_f = safe_float(weather.get("feels_like"))
    humidity = safe_float(weather.get("humidity"))

    irrigation_context = summarize_irrigation_context(sprinkler)

    camera_rain_detected = bool(rain_detection.get("rain_detected"))
    camera_rain_confidence = str(rain_detection.get("confidence") or "unknown")
    camera_wetness_score = normalize_dryness(rain_detection.get("wetness_score"))
    camera_motion_score = normalize_dryness(rain_detection.get("motion_score"))

    lawn_need = classify_lawn_need(
        grass_score=grass_score,
        dryness_index=dryness_index,
        rain_probability=rain_probability,
        temp_f=feels_like_f if feels_like_f is not None else temp_f,
        humidity=humidity,
    )

    recommendation = "monitor_lawn"
    confidence = "medium"
    reason = "Environmental conditions are stable. Continue monitoring lawn condition and weather."

    safety = {
        "auto_execute_allowed": False,
        "requires_user_approval": True,
        "reason": "Environmental recommendations are advisory unless explicitly approved.",
    }

    # ----------------------------------------------------
    # Highest-priority: sprinkler is already running.
    # ----------------------------------------------------
    if irrigation_context["running"]:
        if rain_probability >= 0.55:
            recommendation = "stop_or_delay_irrigation"
            confidence = "high"
            reason = (
                "Sprinkler is running while rain probability is elevated. "
                "Orion recommends stopping or delaying irrigation to avoid unnecessary watering."
            )
        elif lawn_need["need_level"] in {"high", "moderate"}:
            recommendation = "continue_irrigation_monitor"
            confidence = "medium"
            reason = (
                "Sprinkler is running and lawn condition indicates some watering need. "
                "Continue monitoring weather and lawn response."
            )
        else:
            recommendation = "monitor_irrigation"
            confidence = "medium"
            reason = (
                "Sprinkler is running, but current lawn and weather indicators do not show urgent watering need."
            )

    # ----------------------------------------------------
    # Rain dominates irrigation decisions.
    # ----------------------------------------------------
    elif rain_probability >= 0.7:
        recommendation = "delay_irrigation"
        confidence = "high"

        if camera_rain_detected:
            reason = (
                "Rain probability is high and the environmental camera shows rain or wet-surface evidence. "
                "Delay irrigation and continue monitoring lawn condition."
            )
        else:
            reason = (
                "Rain probability is high. Delay irrigation and continue monitoring lawn condition. "
                "Camera has not visually confirmed active rain at this moment."
            )

    elif rain_probability >= 0.45 and lawn_need["need_level"] != "high":
        recommendation = "delay_irrigation"
        confidence = "high" if camera_rain_detected else "medium"

        if camera_rain_detected:
            reason = (
                "Rain is possible and the environmental camera shows rain or wet-surface evidence. "
                "Delay irrigation and monitor whether rainfall improves lawn condition."
            )
        else:
            reason = (
                "Rain is possible and lawn watering need is not high. "
                "Delay irrigation and monitor whether rainfall improves lawn condition."
            )

    # ----------------------------------------------------
    # Healthy / low need.
    # ----------------------------------------------------
    elif lawn_need["need_level"] == "minimal":
        recommendation = "no_irrigation_needed"
        confidence = "high"
        reason = (
            "Grass condition and dryness indicators do not show a current need for irrigation."
        )

    elif lawn_need["need_level"] == "low":
        recommendation = "monitor_lawn"
        confidence = "medium"
        reason = (
            "Grass condition shows mild or limited stress. Continue monitoring before watering."
        )

    # ----------------------------------------------------
    # Moderate need.
    # ----------------------------------------------------
    elif lawn_need["need_level"] == "moderate":
        recommendation = "monitor_lawn"
        confidence = "medium"

        if irrigation_context["next_irrigation"]:
            reason = (
                "Grass condition shows moderate watering need, but an irrigation run is already scheduled. "
                "Monitor lawn condition and allow the scheduled run unless rain increases."
            )
        else:
            reason = (
                "Grass condition shows moderate watering need with low rain probability. "
                "Consider scheduling irrigation if conditions do not improve."
            )

    # ----------------------------------------------------
    # High need.
    # ----------------------------------------------------
    elif lawn_need["need_level"] == "high":
        if irrigation_context["next_irrigation"]:
            recommendation = "monitor_scheduled_irrigation"
            confidence = "medium"
            reason = (
                "Grass condition indicates high watering need, and irrigation is already scheduled. "
                "Monitor the next run and verify lawn response afterward."
            )
        else:
            recommendation = "consider_irrigation"
            confidence = "high"

            if lawn_need["extreme_heat"]:
                reason = (
                    "Grass condition indicates high watering need with extreme heat and low rain probability. "
                    "Consider an early morning irrigation run."
                )
            else:
                reason = (
                    "Grass condition indicates high watering need with low rain probability. "
                    "Consider irrigation after checking local watering rules."
                )

    return {
        "recommendation": recommendation,
        "confidence": confidence,
        "reason": reason,
        "safety": safety,
        "inputs": {
            "grass_score": round(grass_score, 3),
            "dryness_index": round(dryness_index, 3),
            "rain_probability": round(rain_probability, 3),
            "temperature_f": temp_f,
            "feels_like_f": feels_like_f,
            "humidity": humidity,
            "lawn_need_score": lawn_need["need_score"],
            "lawn_need_level": lawn_need["need_level"],
            "heat_stress": lawn_need["heat_stress"],
            "extreme_heat": lawn_need["extreme_heat"],
            "low_humidity": lawn_need["low_humidity"],
            "camera_rain_detected": camera_rain_detected,
            "camera_rain_confidence": camera_rain_confidence,
            "camera_wetness_score": round(camera_wetness_score, 3),
            "camera_motion_score": round(camera_motion_score, 3),
        },
        "rain_detection": rain_detection,
        "irrigation": irrigation_context,
    }
