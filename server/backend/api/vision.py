import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from flask import Response, jsonify, request


VISION_NODE_URL = os.getenv("VISION_NODE_URL", "http://192.168.7.238:5000").rstrip("/")
VISION_TIMEOUT = float(os.getenv("VISION_TIMEOUT", "3.0"))


def _json_error(message: str, status: int = 500, **extra):
    payload = {
        "ok": False,
        "error": message,
        "vision_node_url": VISION_NODE_URL,
    }
    payload.update(extra)
    return jsonify(payload), status


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


def get_vision_status() -> dict[str, Any]:
    payload = _read_json(f"{VISION_NODE_URL}/api/status")
    return _normalize_status(payload)


def register_vision(app):
    @app.route("/v1/vision/status", methods=["GET"])
    def vision_status():
        try:
            return jsonify(get_vision_status())
        except urllib.error.URLError as e:
            return _json_error(
                "Vision node unreachable",
                503,
                detail=str(e),
                online=False,
            )
        except Exception as e:
            return _json_error(
                "Failed to read vision node status",
                500,
                detail=str(e),
                online=False,
            )

    @app.route("/v1/vision/snapshot", methods=["GET"])
    def vision_snapshot():
        try:
            data, content_type = _read_bytes(f"{VISION_NODE_URL}/api/snapshot")
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
            )

        try:
            result = _post_json(
                f"{VISION_NODE_URL}/api/camera/focus",
                {
                    "mode": mode,
                    "manual_lens_position": lens_position,
                },
            )

            return jsonify(
                {
                    "ok": True,
                    "result": result,
                    "status": get_vision_status(),
                }
            )
        except urllib.error.URLError as e:
            return _json_error(
                "Vision focus command failed",
                503,
                detail=str(e),
            )
        except Exception as e:
            return _json_error(
                "Failed to send focus command",
                500,
                detail=str(e),
            )

    @app.route("/v1/vision/offer", methods=["POST"])
    def vision_offer():
        data = request.json or {}

        if not data.get("sdp") or not data.get("type"):
            return _json_error("Missing WebRTC offer SDP/type.", 400)

        try:
            answer = _post_json(
                f"{VISION_NODE_URL}/offer",
                {
                    "sdp": data.get("sdp"),
                    "type": data.get("type"),
                },
                timeout=max(VISION_TIMEOUT, 10.0),
            )

            return jsonify(answer)
        except urllib.error.URLError as e:
            return _json_error(
                "Vision WebRTC offer failed",
                503,
                detail=str(e),
            )
        except Exception as e:
            return _json_error(
                "Failed to negotiate vision stream",
                500,
                detail=str(e),
            )

    @app.route("/v1/vision/restart-camera", methods=["POST"])
    def vision_restart_camera():
        try:
            result = _post_json(f"{VISION_NODE_URL}/api/camera/restart", {})
            return jsonify(
                {
                    "ok": True,
                    "result": result,
                    "status": get_vision_status(),
                }
            )
        except urllib.error.URLError as e:
            return _json_error(
                "Vision camera restart failed",
                503,
                detail=str(e),
            )
        except Exception as e:
            return _json_error(
                "Failed to restart vision camera",
                500,
                detail=str(e),
            )
