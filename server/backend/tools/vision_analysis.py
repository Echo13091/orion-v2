from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def decode_image_bytes(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("Failed to decode snapshot image")

    return image


def crop_roi(
    image: np.ndarray,
    roi: Optional[Dict[str, float]] = None,
) -> Tuple[np.ndarray, Dict[str, int]]:
    roi = roi or {
        "x": 0.02,
        "y": 0.25,
        "w": 0.90,
        "h": 0.55,
    }

    h, w = image.shape[:2]

    x = clamp(safe_float(roi.get("x"), 0.02), 0.0, 1.0)
    y = clamp(safe_float(roi.get("y"), 0.25), 0.0, 1.0)
    rw = clamp(safe_float(roi.get("w"), 0.90), 0.05, 1.0)
    rh = clamp(safe_float(roi.get("h"), 0.55), 0.05, 1.0)

    x1 = int(w * x)
    y1 = int(h * y)
    x2 = int(w * min(1.0, x + rw))
    y2 = int(h * min(1.0, y + rh))

    if x2 <= x1 or y2 <= y1:
        return image, {
            "x": 0,
            "y": 0,
            "w": w,
            "h": h,
        }

    return image[y1:y2, x1:x2], {
        "x": x1,
        "y": y1,
        "w": x2 - x1,
        "h": y2 - y1,
    }


def analyze_rain_detection_from_images(
    image_a: np.ndarray,
    image_b: Optional[np.ndarray] = None,
    roi: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    if image_a is None:
        return {
            "ok": False,
            "error": "No image available for rain detection",
            "source": "jetson_snapshot_analysis",
        }

    crop_a, roi_pixels = crop_roi(image_a, roi)

    if crop_a.size == 0:
        return {
            "ok": False,
            "error": "Invalid rain detection ROI",
            "source": "jetson_snapshot_analysis",
        }

    hsv = cv2.cvtColor(crop_a, cv2.COLOR_BGR2HSV)

    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]

    total_count = int(crop_a.shape[0] * crop_a.shape[1])

    mean_brightness = float(np.mean(val)) / 255.0
    bright_ratio = float(np.count_nonzero(val > 165)) / max(1, total_count)

    dark_ratio = float(np.count_nonzero(val < 75)) / max(1, total_count)
    low_saturation_ratio = float(np.count_nonzero(sat < 55)) / max(1, total_count)
    bright_reflection_ratio = float(
        np.count_nonzero((val > 185) & (sat < 90))
    ) / max(1, total_count)

    gray_a = cv2.cvtColor(crop_a, cv2.COLOR_BGR2GRAY)
    blur_a = cv2.GaussianBlur(gray_a, (7, 7), 0)

    texture_score = float(cv2.Laplacian(blur_a, cv2.CV_64F).var())
    smoothness_score = clamp(1.0 - (texture_score / 650.0), 0.0, 1.0)

    motion_score = 0.0

    if image_b is not None:
        crop_b, _ = crop_roi(image_b, roi)

        if crop_b.size != 0 and crop_b.shape == crop_a.shape:
            gray_b = cv2.cvtColor(crop_b, cv2.COLOR_BGR2GRAY)
            blur_b = cv2.GaussianBlur(gray_b, (7, 7), 0)

            diff = cv2.absdiff(blur_a, blur_b)
            motion_score = float(np.mean(diff)) / 255.0
            motion_score = clamp(motion_score * 6.0, 0.0, 1.0)

    wet_surface_score = (
        dark_ratio * 0.42
        + low_saturation_ratio * 0.24
        + bright_reflection_ratio * 0.08
        + smoothness_score * 0.16
        + motion_score * 0.10
    )

    wetness_score = clamp(wet_surface_score, 0.0, 1.0)

    active_rain_detected = (
        motion_score >= 0.10 and wetness_score >= 0.22
    )

    # Be conservative:
    # - Do not treat reflection alone as wet pavement.
    # - Require multiple visual signals, because bright cars/driveways can look reflective.
    wet_surface_evidence = (
        wetness_score >= 0.45
        or (dark_ratio >= 0.35 and low_saturation_ratio >= 0.35)
        or (
            wetness_score >= 0.30
            and dark_ratio >= 0.25
            and low_saturation_ratio >= 0.30
        )
        or (
            dark_ratio >= 0.25
            and low_saturation_ratio >= 0.30
            and bright_reflection_ratio >= 0.08
        )
    )

    rain_detected = active_rain_detected or wet_surface_evidence

    if active_rain_detected:
        visual_evidence_type = "raining"
        label = "Raining"
        confidence = "high"
        reason = "Camera evidence suggests active rainfall or moving rain artifacts."
    elif wet_surface_evidence:
        visual_evidence_type = "wet_surface"
        label = "Wet Surface"
        confidence = "high" if wetness_score >= 0.45 else "medium"
        reason = "Camera evidence suggests wet outdoor surfaces."
    elif wetness_score >= 0.20 or bright_reflection_ratio >= 0.05:
        visual_evidence_type = "surface_moisture"
        label = "Surface Moisture"
        confidence = "medium"
        reason = "Camera evidence suggests possible surface moisture, but not enough to classify active rainfall."
    elif mean_brightness <= 0.18 or dark_ratio >= 0.75:
        visual_evidence_type = "dark_low_light"
        label = "Dark / Low Light"
        confidence = "medium"
        reason = "Camera scene is dark or low-light; wet surface classification is limited."
    elif mean_brightness >= 0.52 and bright_ratio >= 0.25:
        visual_evidence_type = "bright_dry"
        label = "Bright / Dry"
        confidence = "medium"
        reason = "Camera scene appears bright with no strong wet-surface indicators."
    else:
        visual_evidence_type = "clear_dry"
        label = "Clear / Dry"
        confidence = "medium"
        reason = "Camera scene does not show strong wet-surface or active rainfall indicators."

    return {
        "ok": True,
        "rain_detected": rain_detected,
        "active_rain_detected": active_rain_detected,
        "wet_surface_evidence": wet_surface_evidence,
        "visual_evidence_detected": rain_detected,
        "visual_evidence_type": visual_evidence_type,
        "visual_evidence_label": label,
        "confidence": confidence,
        "wetness_score": round(wetness_score, 3),
        "motion_score": round(motion_score, 3),
        "dark_percent": round(dark_ratio * 100, 1),
        "low_saturation_percent": round(low_saturation_ratio * 100, 1),
        "reflection_percent": round(bright_reflection_ratio * 100, 1),
        "brightness_score": round(mean_brightness, 3),
        "bright_percent": round(bright_ratio * 100, 1),
        "smoothness_score": round(smoothness_score, 3),
        "roi": roi_pixels,
        "reason": reason,
        "source": "jetson_snapshot_analysis",
        "time": now_iso(),
    }


def analyze_rain_detection_from_bytes(
    image_a_bytes: bytes,
    image_b_bytes: Optional[bytes] = None,
    roi: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    image_a = decode_image_bytes(image_a_bytes)
    image_b = decode_image_bytes(image_b_bytes) if image_b_bytes else None

    return analyze_rain_detection_from_images(
        image_a=image_a,
        image_b=image_b,
        roi=roi,
    )
