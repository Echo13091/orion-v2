import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


NODE_URL = os.getenv("ORION_ENV_VISION_NODE_URL", "http://192.168.7.211").rstrip("/")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("ORION_ENV_VISION_TIMEOUT_SECONDS", "3.0"))

EVIDENCE_DIR = Path(os.getenv("ORION_VISION_EVIDENCE_DIR", "/tmp/orion-vision-evidence"))
LATEST_SNAPSHOT = EVIDENCE_DIR / "latest.jpg"
LATEST_METADATA = EVIDENCE_DIR / "latest.json"


def _get_json(path: str) -> Dict[str, Any]:
    req = urllib.request.Request(
        f"{NODE_URL}{path}",
        headers={
            "Accept": "application/json",
            "User-Agent": "orion-v2-vision-evidence",
        },
        method="GET",
    )

    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def _safe_get_json(path: str) -> Tuple[Dict[str, Any], Optional[str]]:
    try:
        data = _get_json(path)
        return data if isinstance(data, dict) else {}, None
    except Exception as exc:
        return {}, str(exc)


def _capture_snapshot() -> Tuple[bool, Optional[int], Optional[str]]:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    req = urllib.request.Request(
        f"{NODE_URL}/capture",
        headers={
            "Accept": "image/jpeg",
            "User-Agent": "orion-v2-vision-evidence",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            content_type = response.headers.get("Content-Type", "")
            data = response.read()

        if "image/jpeg" not in content_type.lower():
            return False, None, f"Unexpected content type: {content_type}"

        if len(data) < 512:
            return False, len(data), "Snapshot too small to trust"

        LATEST_SNAPSHOT.write_bytes(data)
        return True, len(data), None

    except Exception as exc:
        return False, None, str(exc)


def _load_latest_metadata() -> Optional[Dict[str, Any]]:
    try:
        if not LATEST_METADATA.exists():
            return None
        return json.loads(LATEST_METADATA.read_text())
    except Exception:
        return None


def get_vision_evidence(capture: bool = True) -> Dict[str, Any]:
    checked_at = time.time()

    status, status_error = _safe_get_json("/status")
    camera, camera_error = _safe_get_json("/api/camera")

    wifi = status.get("wifi", {}) if isinstance(status.get("wifi"), dict) else {}

    node_ok = bool(status.get("ok"))
    camera_enabled = bool(camera.get("camera_enabled"))
    camera_ready = bool(camera.get("camera_ready"))

    snapshot_ok = False
    snapshot_size = None
    snapshot_error = None

    if capture and node_ok and camera_ready:
        snapshot_ok, snapshot_size, snapshot_error = _capture_snapshot()
    elif capture:
        snapshot_error = "Node or camera not ready"

    snapshot_available = snapshot_ok or LATEST_SNAPSHOT.exists()

    evidence = {
        "ok": bool(node_ok and camera_ready and (snapshot_ok or not capture)),
        "source": "esp32_environmental_vision",
        "type": "environmental_snapshot",
        "node_url": NODE_URL,
        "checked_at": checked_at,
        "captured_at": checked_at if snapshot_ok else None,
        "node_health": "online" if node_ok else "offline",
        "camera_enabled": camera_enabled,
        "camera_ready": camera_ready,
        "snapshot_requested": capture,
        "snapshot_available": snapshot_available,
        "snapshot_updated": snapshot_ok,
        "snapshot_size_bytes": snapshot_size,
        "snapshot_url": "/v1/vision/evidence/latest.jpg" if snapshot_available else None,
        "wifi": {
            "status": wifi.get("status"),
            "ip": wifi.get("ip"),
            "rssi": wifi.get("rssi"),
            "ssid": wifi.get("ssid"),
        },
        "errors": {
            "status": status_error,
            "camera": camera_error,
            "snapshot": snapshot_error,
        },
        "raw_status": status,
        "camera": camera,
        "previous": _load_latest_metadata(),
        "usable_for_automation": bool(node_ok and camera_ready and snapshot_available),
        "notes": "Snapshot evidence is intended for environmental context and decision support. MJPEG stream remains manual inspection only.",
    }

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_METADATA.write_text(json.dumps(evidence, indent=2, sort_keys=True))
    return evidence


def latest_snapshot_path() -> Optional[Path]:
    if LATEST_SNAPSHOT.exists():
        return LATEST_SNAPSHOT
    return None
