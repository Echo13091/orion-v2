import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple


DEFAULT_NODE_URL = "http://192.168.7.211"

NODE_URL = os.getenv("ORION_ENV_VISION_NODE_URL", DEFAULT_NODE_URL).rstrip("/")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("ORION_ENV_VISION_TIMEOUT_SECONDS", "2.5"))


def _get_json(path: str) -> Dict[str, Any]:
    url = f"{NODE_URL}{path}"

    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "orion-v2-environmental-vision-probe",
        },
        method="GET",
    )

    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        raw = response.read().decode("utf-8", errors="replace")

    return json.loads(raw)


def _safe_get_json(path: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        return _get_json(path), None
    except urllib.error.URLError as exc:
        return None, str(exc)
    except TimeoutError as exc:
        return None, str(exc)
    except Exception as exc:
        return None, str(exc)


def _vision_payload() -> Dict[str, Any]:
    checked_at = time.time()

    status, status_error = _safe_get_json("/status")
    camera, camera_error = _safe_get_json("/api/camera")

    status = status if isinstance(status, dict) else {}
    camera = camera if isinstance(camera, dict) else {}

    wifi = status.get("wifi", {}) if isinstance(status.get("wifi"), dict) else {}
    ap = status.get("ap", {}) if isinstance(status.get("ap"), dict) else {}

    node_ok = bool(status.get("ok"))
    camera_ready = bool(camera.get("camera_ready"))
    camera_enabled = bool(camera.get("camera_enabled"))

    if node_ok and camera_ready:
        health = "online"
    elif node_ok:
        health = "degraded"
    else:
        health = "offline"

    message = (
        "ESP32-S3 environmental vision node is online and camera-ready."
        if health == "online"
        else "ESP32-S3 node is reachable, but the camera is not ready."
        if health == "degraded"
        else "ESP32-S3 environmental vision node is unreachable."
    )

    return {
        "id": "esp32_environmental_vision",
        "name": "ESP32-S3 Environmental Vision Node",
        "vendor": "Freenove / ESP32-S3",
        "model": "ESP32-S3-WROOM Camera Node",
        "device": status.get("device") or "orion-esp32-s3-vision",
        "firmware_version": status.get("firmware_version"),
        "integration_type": "local_environmental_vision",
        "managed_by": "Orion V2",
        "location": os.getenv("ORION_ENV_VISION_LOCATION", "Environmental Monitoring"),
        "orion_role": "Environmental vision node",
        "health": health,
        "reachable": node_ok,
        "camera_enabled": camera_enabled,
        "camera_ready": camera_ready,
        "stream_access": camera_ready,
        "capture_access": camera_ready,
        "local_access": node_ok,
        "ptz_control": "not_supported",
        "node_url": NODE_URL,
        "status_url": f"{NODE_URL}/status",
        "camera_status_url": f"{NODE_URL}/api/camera",
        "capture_url": f"{NODE_URL}/capture",
        "stream_url": f"{NODE_URL}/stream",
        "setup_ap": {
            "ssid": ap.get("ssid") or wifi.get("ap_ssid") or "Orion-Vision-Setup",
            "ip": ap.get("ip") or wifi.get("ap_ip") or "192.168.4.1",
        },
        "wifi": {
            "enabled": wifi.get("enabled"),
            "ssid": wifi.get("ssid"),
            "status": wifi.get("status"),
            "ip": wifi.get("ip"),
            "rssi": wifi.get("rssi"),
        },
        "camera": camera or {
            "ok": False,
            "camera_enabled": False,
            "camera_ready": False,
            "camera_error": camera_error or "camera_status_unavailable",
        },
        "raw_status": status,
        "last_checked": checked_at,
        "message": message,
        "notes": (
            "Local ESP32-S3 environmental camera node. Orion uses this for "
            "visual context, snapshots, camera health, and environmental evidence. "
            "MJPEG stream is available for manual viewing; snapshots are preferred "
            "for automation evidence."
        ),
        "error": camera_error or status_error,
        "capabilities": {
            "local_stream": camera_ready,
            "local_capture": camera_ready,
            "http_ui": node_ok,
            "rtsp": False,
            "onvif": False,
            "ptz": False,
            "orion_health_monitoring": True,
            "environmental_snapshot": camera_ready,
            "vendor_app_live_view": False,
            "vendor_app_ptz": False,
            "vendor_app_motion_alerts": False,
            "vendor_app_playback": False,
        },
    }


def get_camera_status() -> Dict[str, Any]:
    device = _vision_payload()

    return {
        "system": "environmental_vision",
        "summary": {
            "total": 1,
            "online": 1 if device["health"] == "online" else 0,
            "degraded": 1 if device["health"] == "degraded" else 0,
            "offline": 1 if device["health"] == "offline" else 0,
            "native_streams": 1 if device["stream_access"] else 0,
            "local_capture": 1 if device["capture_access"] else 0,
            "external_cloud": 0,
        },
        "devices": [device],
    }
