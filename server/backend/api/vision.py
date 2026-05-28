import colorsys
import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from tools.vision_analysis import analyze_rain_detection_from_bytes
from flask import Response, jsonify, request
from core.event_store import record_event
from core.state import update_state


VISION_NODE_URL = os.getenv("VISION_NODE_URL", "http://192.168.7.218:5000").rstrip("/")
VISION_NODE_FALLBACK_URL = os.getenv("VISION_NODE_FALLBACK_URL", "").rstrip("/")
VISION_NODE_URLS = [url for url in [VISION_NODE_URL, VISION_NODE_FALLBACK_URL] if url]
VISION_TIMEOUT = float(os.getenv("VISION_TIMEOUT", "3.0"))

VISION_EVENT_THROTTLE_SECONDS = float(os.getenv("VISION_EVENT_THROTTLE_SECONDS", "300"))
_LAST_VISION_OFFLINE_EVENT_TS = 0.0
_LAST_VISION_RECOVERY_EVENT_TS = 0.0
_VISION_WAS_OFFLINE = False


def _vision_degraded_payload(message: str, detail: str = "", **extra) -> dict[str, Any]:
    payload = {
        "ok": False,
        "online": False,
        "degraded": True,
        "mode": "vision_degraded",
        "analysis_available": False,
        "error": message,
        "message": message,
        "detail": detail,
        "vision_node_url": VISION_NODE_URL,
        "vision_node_fallback_url": VISION_NODE_FALLBACK_URL or None,
        "vision_node_urls": VISION_NODE_URLS,
        "configured_node_urls": VISION_NODE_URLS,
    }
    payload.update(extra)
    return payload


def _json_error(message: str, status: int = 500, **extra):
    detail = str(extra.pop("detail", "") or "")
    payload = _vision_degraded_payload(message, detail=detail, **extra)
    return jsonify(payload), status


def _record_vision_offline_event(detail: str = "") -> None:
    global _LAST_VISION_OFFLINE_EVENT_TS
    global _VISION_WAS_OFFLINE

    now = time.time()

    if now - _LAST_VISION_OFFLINE_EVENT_TS < VISION_EVENT_THROTTLE_SECONDS:
        _VISION_WAS_OFFLINE = True
        return

    _LAST_VISION_OFFLINE_EVENT_TS = now
    _VISION_WAS_OFFLINE = True

    record_event(
        subsystem="vision",
        node="vision-node",
        severity="warning",
        event_type="node_offline",
        message="Vision node unreachable",
        source="vision_status",
        evidence={
            "vision_node_url": VISION_NODE_URL,
            "vision_node_fallback_url": VISION_NODE_FALLBACK_URL or None,
            "vision_node_urls": VISION_NODE_URLS,
            "detail": detail,
            "throttle_seconds": VISION_EVENT_THROTTLE_SECONDS,
        },
    )


def _record_vision_recovery_event(active_url: str = "") -> None:
    global _LAST_VISION_RECOVERY_EVENT_TS
    global _VISION_WAS_OFFLINE

    if not _VISION_WAS_OFFLINE:
        return

    now = time.time()

    if now - _LAST_VISION_RECOVERY_EVENT_TS < VISION_EVENT_THROTTLE_SECONDS:
        _VISION_WAS_OFFLINE = False
        return

    _LAST_VISION_RECOVERY_EVENT_TS = now
    _VISION_WAS_OFFLINE = False

    record_event(
        subsystem="vision",
        node="vision-node",
        severity="info",
        event_type="node_recovered",
        message="Vision node recovered",
        source="vision_status",
        evidence={
            "active_node_url": active_url or None,
            "vision_node_url": VISION_NODE_URL,
            "vision_node_fallback_url": VISION_NODE_FALLBACK_URL or None,
            "vision_node_urls": VISION_NODE_URLS,
        },
    )


def _read_json(url: str, timeout: float = VISION_TIMEOUT) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
        },
        method="GET",
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")

    return json.loads(raw)


def _post_json(url: str, payload: dict[str, Any], timeout: float = VISION_TIMEOUT) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")

    return json.loads(raw)


def _read_bytes(url: str, timeout: float = VISION_TIMEOUT):
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "image/jpeg",
        },
        method="GET",
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        content_type = resp.headers.get("Content-Type", "application/octet-stream")
        data = resp.read()

    return data, content_type


def _normalize_status(payload: dict[str, Any]) -> dict[str, Any]:
    settings = payload.get("settings") if isinstance(payload.get("settings"), dict) else {}
    state = payload.get("state") if isinstance(payload.get("state"), dict) else {}

    online = bool(payload.get("ok")) and bool(state.get("online")) and bool(state.get("camera_online"))
    fault = bool(state.get("fault"))

    return {
        "ok": True,
        "online": online,
        "node_url": VISION_NODE_URL,
        "node_id": settings.get("node_id", "vision_node_1"),
        "node_name": settings.get("node_name", "Orion Vision Node"),
        "camera_online": bool(state.get("camera_online")),
        "streaming_clients": state.get("streaming_clients", 0),
        "recording": bool(state.get("recording")),
        "fps": state.get("fps"),
        "resolution": state.get("resolution") or settings.get("video_resolution"),
        "focus_mode": state.get("focus_mode") or settings.get("focus_mode"),
        "focus_state": state.get("focus_state"),
        "lens_position": state.get("lens_position"),
        "uptime_seconds": state.get("uptime_seconds"),
        "last_frame_age": state.get("last_frame_age"),
        "fault": fault,
        "fault_code": state.get("fault_code", ""),
        "fault_message": state.get("fault_message", ""),
        "raw": payload,
    }


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _normalized_roi_box(
    settings: dict[str, Any],
    roi_key: str,
    width: int,
    height: int,
    default: tuple[float, float, float, float],
) -> tuple[int, int, int, int]:
    roi = settings.get(roi_key) if isinstance(settings.get(roi_key), dict) else {}

    x = _clamp(float(roi.get("x", default[0])), 0.0, 1.0)
    y = _clamp(float(roi.get("y", default[1])), 0.0, 1.0)
    w = _clamp(float(roi.get("w", default[2])), 0.01, 1.0)
    h = _clamp(float(roi.get("h", default[3])), 0.01, 1.0)

    left = int(width * x)
    top = int(height * y)
    right = int(width * _clamp(x + w, 0.0, 1.0))
    bottom = int(height * _clamp(y + h, 0.0, 1.0))

    if right <= left:
        right = min(width, left + 1)
    if bottom <= top:
        bottom = min(height, top + 1)

    return left, top, right, bottom


def _load_snapshot_image():
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "Pillow is required for Jetson-side vision analysis. "
            "Install it with: pip install Pillow"
        ) from exc

    status_payload, active_node_url = _try_read_json("/api/status")
    settings = status_payload.get("settings") if isinstance(status_payload.get("settings"), dict) else {}

    data, _content_type = _read_bytes(
        f"{active_node_url}/api/snapshot",
        timeout=max(VISION_TIMEOUT, 10.0),
    )

    image = Image.open(io.BytesIO(data)).convert("RGB")
    return image, settings, status_payload


def _downsample_crop(image, box: tuple[int, int, int, int], max_size=(320, 180)):
    crop = image.crop(box)
    crop.thumbnail(max_size)
    return crop


def _analyze_grass_from_snapshot() -> dict[str, Any]:
    image, settings, status_payload = _load_snapshot_image()
    width, height = image.size

    box = _normalized_roi_box(
        settings,
        "grass_roi",
        width,
        height,
        default=(0.0, 0.52, 0.62, 0.45),
    )

    crop = _downsample_crop(image, box)
    pixels = list(crop.getdata())
    total = max(len(pixels), 1)

    green_pixels = 0
    dry_pixels = 0
    dark_pixels = 0
    green_dominance_sum = 0.0
    saturation_sum = 0.0
    brightness_sum = 0.0

    for r, g, b in pixels:
        rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
        hue, saturation, value = colorsys.rgb_to_hsv(rf, gf, bf)

        saturation_sum += saturation
        brightness_sum += value
        green_dominance_sum += max(0.0, (g - max(r, b)) / 255.0)

        is_green = (
            0.18 <= hue <= 0.48
            and saturation >= 0.18
            and value >= 0.15
            and g > r * 1.05
            and g > b * 1.05
        )
        is_dry = (
            0.04 <= hue <= 0.17
            and saturation >= 0.16
            and value >= 0.18
            and r >= g * 0.95
            and g >= b * 0.90
        )
        is_dark = value < 0.12

        if is_green:
            green_pixels += 1
        if is_dry:
            dry_pixels += 1
        if is_dark:
            dark_pixels += 1

    green_ratio = green_pixels / total
    dry_ratio = dry_pixels / total
    dark_ratio = dark_pixels / total
    avg_saturation = saturation_sum / total
    avg_brightness = brightness_sum / total
    avg_green_dominance = green_dominance_sum / total

    score = round(
        _clamp(
            (green_ratio * 100.0)
            + (avg_green_dominance * 80.0)
            - (dry_ratio * 35.0)
            - (dark_ratio * 20.0),
            0.0,
            100.0,
        ),
        1,
    )

    if score >= 60:
        condition = "good"
        recommendation = "Grass color looks healthy in the configured ROI."
    elif score >= 35:
        condition = "fair"
        recommendation = "Grass color is mixed. Keep monitoring before changing irrigation."
    else:
        condition = "poor"
        recommendation = "Grass appears dry, dark, or low-green in the configured ROI."

    green_percent = round(green_ratio * 100.0, 1)
    dry_percent = round(dry_ratio * 100.0, 1)
    valid_percent = round((1.0 - dark_ratio) * 100.0, 1)
    dryness_index = round(_clamp((dry_ratio * 0.75) + ((100.0 - score) / 100.0 * 0.25), 0.0, 1.0), 3)

    return {
        "ok": True,
        "source": "orion_jetson_snapshot_analysis",
        "node_url": VISION_NODE_URL,
        "condition": condition,
        "grass_condition": condition,
        "score": score,
        "confidence": "medium",
        "recommendation": recommendation,
        "reason": recommendation,
        "dryness_index": dryness_index,
        "green_percent": green_percent,
        "dry_percent": dry_percent,
        "valid_percent": valid_percent,
        "metrics": {
            "green_ratio": round(green_ratio, 4),
            "dry_ratio": round(dry_ratio, 4),
            "dark_ratio": round(dark_ratio, 4),
            "avg_saturation": round(avg_saturation, 4),
            "avg_brightness": round(avg_brightness, 4),
            "avg_green_dominance": round(avg_green_dominance, 4),
        },
        "roi": {
            "left": box[0],
            "top": box[1],
            "right": box[2],
            "bottom": box[3],
            "image_width": width,
            "image_height": height,
        },
        "vision_status": _normalize_status(status_payload),
    }


def _analyze_rain_from_snapshot() -> dict[str, Any]:
    image, settings, status_payload = _load_snapshot_image()
    width, height = image.size

    box = _normalized_roi_box(
        settings,
        "rain_roi",
        width,
        height,
        default=(0.05, 0.28, 0.78, 0.52),
    )

    crop = _downsample_crop(image, box)
    pixels = list(crop.getdata())
    total = max(len(pixels), 1)

    low_saturation_pixels = 0
    bright_reflection_pixels = 0
    dark_wet_pixels = 0
    saturation_sum = 0.0
    brightness_sum = 0.0

    for r, g, b in pixels:
        rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
        _hue, saturation, value = colorsys.rgb_to_hsv(rf, gf, bf)

        saturation_sum += saturation
        brightness_sum += value

        if saturation <= 0.18 and value >= 0.28:
            low_saturation_pixels += 1
        if saturation <= 0.22 and value >= 0.72:
            bright_reflection_pixels += 1
        if saturation <= 0.25 and 0.12 <= value <= 0.38:
            dark_wet_pixels += 1

    low_sat_ratio = low_saturation_pixels / total
    reflection_ratio = bright_reflection_pixels / total
    dark_wet_ratio = dark_wet_pixels / total
    avg_saturation = saturation_sum / total
    avg_brightness = brightness_sum / total

    evidence_score = round(
        _clamp(
            (low_sat_ratio * 45.0)
            + (reflection_ratio * 70.0)
            + (dark_wet_ratio * 35.0)
            - (avg_saturation * 15.0),
            0.0,
            100.0,
        ),
        1,
    )

    rain_detected = evidence_score >= 35.0

    if rain_detected:
        summary = "Possible rain/wet-surface evidence detected in the configured ROI."
    else:
        summary = "No strong rain/wet-surface evidence detected in the configured ROI."

    wetness_score = round(evidence_score / 100.0, 3)
    motion_score = 0.0
    dark_area_percent = round(dark_wet_ratio * 100.0, 1)
    reflection_percent = round(reflection_ratio * 100.0, 1)

    return {
        "ok": True,
        "source": "orion_jetson_snapshot_analysis",
        "node_url": VISION_NODE_URL,
        "rain_detected": rain_detected,
        "detected": rain_detected,
        "score": evidence_score,
        "confidence": "low" if 25.0 <= evidence_score <= 45.0 else "medium",
        "summary": summary,
        "wetness_score": wetness_score,
        "motion_score": motion_score,
        "dark_area_percent": dark_area_percent,
        "reflection_percent": reflection_percent,
        "metrics": {
            "low_saturation_ratio": round(low_sat_ratio, 4),
            "reflection_ratio": round(reflection_ratio, 4),
            "dark_wet_ratio": round(dark_wet_ratio, 4),
            "avg_saturation": round(avg_saturation, 4),
            "avg_brightness": round(avg_brightness, 4),
        },
        "roi": {
            "left": box[0],
            "top": box[1],
            "right": box[2],
            "bottom": box[3],
            "image_width": width,
            "image_height": height,
        },
        "vision_status": _normalize_status(status_payload),
    }


def _try_read_json(path: str, timeout: float = VISION_TIMEOUT) -> tuple[dict[str, Any], str]:
    last_error: Exception | None = None

    for base_url in VISION_NODE_URLS:
        try:
            payload = _read_json(f"{base_url}{path}", timeout=timeout)
            return payload, base_url
        except Exception as exc:
            last_error = exc

    if last_error:
        raise last_error

    raise RuntimeError("No vision node URLs configured")


def _try_read_bytes(path: str, timeout: float = VISION_TIMEOUT):
    last_error: Exception | None = None

    for base_url in VISION_NODE_URLS:
        try:
            data, content_type = _read_bytes(f"{base_url}{path}", timeout=timeout)
            return data, content_type, base_url
        except Exception as exc:
            last_error = exc

    if last_error:
        raise last_error

    raise RuntimeError("No vision node URLs configured")


def _try_post_json(path: str, payload: dict[str, Any], timeout: float = VISION_TIMEOUT) -> tuple[dict[str, Any], str]:
    last_error: Exception | None = None

    for base_url in VISION_NODE_URLS:
        try:
            result = _post_json(f"{base_url}{path}", payload, timeout=timeout)
            return result, base_url
        except Exception as exc:
            last_error = exc

    if last_error:
        raise last_error

    raise RuntimeError("No vision node URLs configured")


def get_vision_status() -> dict[str, Any]:
    payload, active_url = _try_read_json("/api/status")
    normalized = _normalize_status(payload)
    normalized["node_url"] = active_url
    normalized["configured_node_urls"] = VISION_NODE_URLS
    _record_vision_recovery_event(active_url)
    return normalized


def register_vision(app):
    @app.route("/v1/vision/status", methods=["GET"])
    def vision_status():
        try:
            return jsonify(get_vision_status())
        except urllib.error.URLError as e:
            _record_vision_offline_event(str(e))
            return _json_error(
                "Vision node unreachable",
                503,
                detail=str(e),
                online=False,
            )
        except Exception as e:
            _record_vision_offline_event(str(e))
            return _json_error(
                "Failed to read vision node status",
                503,
                detail=str(e),
                online=False,
            )

    @app.route("/v1/vision/grass-condition", methods=["GET"])
    def vision_grass_condition():
        try:
            payload = _analyze_grass_from_snapshot()
            update_state(grass_condition=payload)
            return jsonify(payload)
        except urllib.error.URLError as e:
            return _json_error(
                "Grass condition analysis unavailable",
                503,
                detail=str(e),
            )
        except Exception as e:
            return _json_error(
                "Failed to analyze grass condition",
                500,
                detail=str(e),
            )

    @app.route("/v1/vision/rain-detection", methods=["GET"])
    def vision_rain_detection():
        try:
            payload = _analyze_rain_from_snapshot()
            update_state(rain_detection=payload)
            return jsonify(payload)
        except urllib.error.URLError as e:
            return _json_error(
                "Jetson camera rain analysis unavailable",
                503,
                detail=str(e),
            )
        except Exception as e:
            return _json_error(
                "Failed to run Jetson camera rain analysis",
                503,
                detail=str(e),
            )

    @app.route("/v1/vision/snapshot", methods=["GET"])
    def vision_snapshot():
        try:
            data, content_type, active_node_url = _try_read_bytes("/api/snapshot")
            return Response(
                data,
                mimetype=content_type,
                headers={
                    "Cache-Control": "no-store",
                },
            )
        except urllib.error.URLError as e:
            return _json_error(
                "Vision snapshot unavailable",
                503,
                detail=str(e),
            )
        except Exception as e:
            return _json_error(
                "Failed to fetch vision snapshot",
                500,
                detail=str(e),
            )

    @app.route("/v1/vision/focus", methods=["POST"])
    def vision_focus():
        data = request.json or {}

        mode = str(data.get("mode") or "continuous").strip().lower()
        lens_position = data.get("manual_lens_position", 3.0)

        if mode not in {"continuous", "auto_once", "manual"}:
            return _json_error(
                "Invalid focus mode. Use continuous, auto_once, or manual.",
                400,
                degraded=False,
                analysis_available=False,
            )

        try:
            result, active_node_url = _try_post_json(
                "/api/camera/focus",
                {
                    "mode": mode,
                    "manual_lens_position": lens_position,
                },
            )

            return jsonify(
                {
                    "ok": True,
                    "online": True,
                    "degraded": False,
                    "active_node_url": active_node_url,
                    "result": result,
                    "status": get_vision_status(),
                }
            )
        except urllib.error.URLError as e:
            _record_vision_offline_event(str(e))
            return _json_error(
                "Vision focus command unavailable because the vision node is offline",
                503,
                detail=str(e),
            )
        except Exception as e:
            _record_vision_offline_event(str(e))
            return _json_error(
                "Failed to send focus command",
                503,
                detail=str(e),
            )

    @app.route("/v1/vision/offer", methods=["POST"])
    def vision_offer():
        data = request.json or {}

        if not data.get("sdp") or not data.get("type"):
            return _json_error(
                "Missing WebRTC offer SDP/type.",
                400,
                degraded=False,
                analysis_available=False,
            )

        try:
            answer, active_node_url = _try_post_json(
                "/offer",
                {
                    "sdp": data.get("sdp"),
                    "type": data.get("type"),
                },
                timeout=max(VISION_TIMEOUT, 10.0),
            )

            if isinstance(answer, dict):
                answer.setdefault("ok", True)
                answer.setdefault("online", True)
                answer.setdefault("degraded", False)
                answer.setdefault("active_node_url", active_node_url)

            return jsonify(answer)
        except urllib.error.URLError as e:
            _record_vision_offline_event(str(e))
            return _json_error(
                "Vision stream unavailable because the vision node is offline",
                503,
                detail=str(e),
            )
        except Exception as e:
            _record_vision_offline_event(str(e))
            return _json_error(
                "Failed to negotiate vision stream",
                503,
                detail=str(e),
            )

    @app.route("/v1/vision/restart-camera", methods=["POST"])
    def vision_restart_camera():
        try:
            result, active_node_url = _try_post_json("/api/camera/restart", {})
            return jsonify(
                {
                    "ok": True,
                    "online": True,
                    "degraded": False,
                    "active_node_url": active_node_url,
                    "result": result,
                    "status": get_vision_status(),
                }
            )
        except urllib.error.URLError as e:
            _record_vision_offline_event(str(e))
            return _json_error(
                "Vision camera restart unavailable because the vision node is offline",
                503,
                detail=str(e),
            )
        except Exception as e:
            _record_vision_offline_event(str(e))
            return _json_error(
                "Failed to restart vision camera",
                503,
                detail=str(e),
            )
