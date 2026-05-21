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


def is_lawn_analysis_available(grass_condition: Dict[str, Any]) -> bool:
    condition = str(grass_condition.get("condition") or "").strip().lower()
    valid_percent = safe_float(grass_condition.get("valid_percent"), 0.0)

    if condition == "unknown":
        return False

    if valid_percent is not None and valid_percent < 5.0:
        return False

    return True


def has_visual_wet_surface_evidence(
    rain_detection: Dict[str, Any],
    rain_probability: float,
) -> bool:
    if not isinstance(rain_detection, dict):
        return False

    if bool(rain_detection.get("rain_detected")):
        return True

    wetness_score = safe_float(rain_detection.get("wetness_score"), 0.0) or 0.0
    motion_score = safe_float(rain_detection.get("motion_score"), 0.0) or 0.0
    dark_percent = safe_float(rain_detection.get("dark_percent"), 0.0) or 0.0
    reflection_percent = safe_float(rain_detection.get("reflection_percent"), 0.0) or 0.0
    low_saturation_percent = safe_float(
        rain_detection.get("low_saturation_percent"),
        0.0,
    ) or 0.0

    # Keep this conservative. Forecast rain probability should not force
    # visual wet-surface confirmation by itself.
    if wetness_score >= 0.45:
        return True

    if dark_percent >= 35.0 and low_saturation_percent >= 35.0:
        return True

    if (
        wetness_score >= 0.30
        and dark_percent >= 25.0
        and low_saturation_percent >= 30.0
    ):
        return True

    if (
        dark_percent >= 25.0
        and low_saturation_percent >= 30.0
        and reflection_percent >= 8.0
    ):
        return True

    if motion_score >= 0.10 and wetness_score >= 0.22:
        return True

    return False


def visual_evidence_label(
    *,
    camera_rain_detected: bool,
    visual_wet_surface_evidence: bool,
) -> str:
    if camera_rain_detected:
        return "Raining"

    if visual_wet_surface_evidence:
        return "Wet Surface"

    return "Clear / Dry"


def extract_next_irrigation(sprinkler: Dict[str, Any]) -> Any:
    raw = sprinkler.get("raw") if is_record(sprinkler.get("raw")) else {}

    next_run = first_present(
        sprinkler.get("next_run"),
        raw.get("next_run"),
        raw.get("next_scheduled_run"),
    )

    if next_run:
        return next_run

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
    lawn_analysis_available: bool = True,
) -> Dict[str, Any]:
    heat_stress = bool(temp_f is not None and temp_f >= 88)
    extreme_heat = bool(temp_f is not None and temp_f >= 94)
    low_humidity = bool(humidity is not None and humidity <= 40)

    if not lawn_analysis_available:
        return {
            "need_score": 0.0,
            "need_level": "unknown",
            "heat_stress": heat_stress,
            "extreme_heat": extreme_heat,
            "low_humidity": low_humidity,
        }

    need_score = 0.0

    need_score += (1.0 - grass_score) * 0.42
    need_score += dryness_index * 0.32

    if heat_stress:
        need_score += 0.12
    if extreme_heat:
        need_score += 0.08
    if low_humidity:
        need_score += 0.06

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

    lawn_analysis_available = is_lawn_analysis_available(grass_condition)

    grass_score = normalize_grass_score(grass_condition.get("score"))
    dryness_index = normalize_dryness(grass_condition.get("dryness_index"))

    if not lawn_analysis_available:
        grass_score = 0.5
        dryness_index = 0.5

    rain_probability = normalize_rain_probability(weather.get("rain_chance"))

    temp_f = safe_float(weather.get("temp"))
    feels_like_f = safe_float(weather.get("feels_like"))
    humidity = safe_float(weather.get("humidity"))

    irrigation_context = summarize_irrigation_context(sprinkler)

    camera_rain_detected = bool(rain_detection.get("rain_detected"))
    visual_wet_surface_evidence = has_visual_wet_surface_evidence(
        rain_detection,
        rain_probability,
    )
    visual_evidence_detected = camera_rain_detected or visual_wet_surface_evidence
    camera_rain_confidence = str(rain_detection.get("confidence") or "unknown")
    camera_wetness_score = normalize_dryness(rain_detection.get("wetness_score"))
    camera_motion_score = normalize_dryness(rain_detection.get("motion_score"))
    camera_visual_label = str(
        rain_detection.get("visual_evidence_label")
        or visual_evidence_label(
            camera_rain_detected=camera_rain_detected,
            visual_wet_surface_evidence=visual_wet_surface_evidence,
        )
    )

    lawn_need = classify_lawn_need(
        grass_score=grass_score,
        dryness_index=dryness_index,
        rain_probability=rain_probability,
        temp_f=feels_like_f if feels_like_f is not None else temp_f,
        humidity=humidity,
        lawn_analysis_available=lawn_analysis_available,
    )

    recommendation = "monitor_lawn"
    confidence = "medium"
    reason = "Environmental conditions are stable. Continue monitoring lawn condition and weather."

    safety = {
        "auto_execute_allowed": False,
        "requires_user_approval": True,
        "reason": "Environmental recommendations are advisory and require operator approval before hardware action.",
    }

    if irrigation_context["running"]:
        if rain_probability >= 0.55 or visual_evidence_detected:
            recommendation = "stop_or_delay_irrigation"
            confidence = "high"
            reason = (
                "Sprinkler is running while rain probability or visual wet-surface evidence is elevated. "
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

    elif rain_probability >= 0.7:
        recommendation = "delay_irrigation"
        confidence = "high"

        if visual_evidence_detected and not lawn_analysis_available:
            reason = (
                "Rain probability is high and the environmental camera shows wet-surface evidence. "
                "Lawn condition is unavailable due to low light or limited visible grass. "
                "Delay irrigation and continue monitoring."
            )
        elif visual_evidence_detected:
            reason = (
                "Rain probability is high and the environmental camera shows wet-surface evidence. "
                "Delay irrigation and continue monitoring lawn condition."
            )
        elif not lawn_analysis_available:
            reason = (
                "Rain probability is high. Lawn condition is unavailable due to low light or limited visible grass. "
                "Delay irrigation and continue monitoring."
            )
        else:
            reason = (
                "Forecast rain probability is high, so Orion recommends holding the next irrigation cycle. "
                f"Camera evidence: {camera_visual_label}."
            )

    elif rain_probability >= 0.45 and lawn_need["need_level"] != "high":
        recommendation = "delay_irrigation"
        confidence = "high" if visual_evidence_detected else "medium"

        if visual_evidence_detected and not lawn_analysis_available:
            reason = (
                "Rain is possible and the environmental camera shows wet-surface evidence. "
                "Lawn condition is unavailable due to low light or limited visible grass. "
                "Delay irrigation and continue monitoring."
            )
        elif visual_evidence_detected:
            reason = (
                "Rain is possible and the environmental camera shows wet-surface evidence. "
                "Delay irrigation and monitor whether rainfall improves lawn condition."
            )
        elif not lawn_analysis_available:
            reason = (
                "Rain is possible. Lawn condition is unavailable due to low light or limited visible grass. "
                "Delay irrigation and continue monitoring."
            )
        else:
            reason = (
                "Rain is possible and lawn watering need is not high. "
                "Delay irrigation and monitor whether rainfall improves lawn condition."
            )

    elif not lawn_analysis_available:
        recommendation = "monitor_lawn"
        confidence = "medium"
        reason = (
            "Lawn condition is unavailable due to low light or limited visible grass. "
            "Continue monitoring and recheck during daylight before making irrigation decisions from camera data."
        )

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
            "lawn_analysis_available": lawn_analysis_available,
            "heat_stress": lawn_need["heat_stress"],
            "extreme_heat": lawn_need["extreme_heat"],
            "low_humidity": lawn_need["low_humidity"],
            "camera_rain_detected": camera_rain_detected,
            "visual_wet_surface_evidence": visual_wet_surface_evidence,
            "visual_evidence_detected": visual_evidence_detected,
            "visual_evidence_label": camera_visual_label,
            "camera_rain_confidence": camera_rain_confidence,
            "camera_wetness_score": round(camera_wetness_score, 3),
            "camera_motion_score": round(camera_motion_score, 3),
        },
        "rain_detection": rain_detection,
        "irrigation": irrigation_context,
    }
