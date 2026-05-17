from __future__ import annotations

from typing import Any, Dict


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


def evaluate_environment(
    *,
    grass_condition: Dict[str, Any] | None,
    weather: Dict[str, Any] | None,
    sprinkler: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    grass_condition = grass_condition or {}
    weather = weather or {}
    sprinkler = sprinkler or {}

    grass_score = normalize_grass_score(grass_condition.get("score"))
    dryness_index = normalize_dryness(
        grass_condition.get("dryness_index")
    )

    rain_probability = normalize_rain_probability(
        weather.get("rain_chance")
    )

    temp_f = weather.get("temp")

    try:
        temp_f = float(temp_f)
    except Exception:
        temp_f = None

    recommendation = "monitor"
    confidence = "medium"
    reason = "Environmental conditions are stable."

    # ----------------------------------------------------
    # Rain priority logic
    # ----------------------------------------------------

    if rain_probability >= 0.7:
        recommendation = "delay_irrigation"
        confidence = "high"
        reason = (
            "Rain probability is high. "
            "Delay irrigation and continue monitoring lawn condition."
        )

    # ----------------------------------------------------
    # Healthy lawn
    # ----------------------------------------------------

    elif grass_score >= 0.65 and dryness_index <= 0.35:
        recommendation = "no_irrigation_needed"
        confidence = "high"
        reason = (
            "Grass condition appears healthy with low dryness indicators."
        )

    # ----------------------------------------------------
    # Mild stress
    # ----------------------------------------------------

    elif grass_score >= 0.4 and dryness_index <= 0.55:
        recommendation = "monitor_lawn"
        confidence = "medium"
        reason = (
            "Grass condition shows moderate stress. "
            "Continue monitoring weather and lawn health."
        )

    # ----------------------------------------------------
    # Dry / stressed lawn
    # ----------------------------------------------------

    elif grass_score < 0.4 or dryness_index > 0.55:
        if rain_probability < 0.3:
            recommendation = "consider_irrigation"
            confidence = "high"

            if temp_f and temp_f >= 88:
                reason = (
                    "Grass condition indicates elevated stress with hot weather "
                    "and low rain probability."
                )
            else:
                reason = (
                    "Grass condition indicates elevated dryness with low rain probability."
                )

        else:
            recommendation = "monitor_lawn"
            confidence = "medium"
            reason = (
                "Grass condition shows stress, but incoming rain may reduce irrigation needs."
            )

    return {
        "recommendation": recommendation,
        "confidence": confidence,
        "reason": reason,
        "inputs": {
            "grass_score": round(grass_score, 3),
            "dryness_index": round(dryness_index, 3),
            "rain_probability": round(rain_probability, 3),
            "temperature_f": temp_f,
        },
    }
