import time
from typing import Any, Dict


CAMERAS = [
    {
        "id": "anran_front_yard",
        "name": "Front Yard Solar Camera",
        "vendor": "ANRAN",
        "model": "Q3/Q3 Pro Solar PTZ",
        "ip": "192.168.50.17",
        "mac_address": "70:3a:2d:39:9a:69",
        "integration_type": "external_cloud",
        "managed_by": "ANRAN App",
        "location": "Front Yard",
        "stream_access": False,
        "local_access": False,
        "ptz_control": "vendor_app",
        "health": "unknown",
        "reachable": None,
        "probe_method": "configuration_only",
        "open_ports": [],
        "message": (
            "Closed vendor camera. Local LAN ports are filtered. "
            "Video, PTZ, motion alerts, and playback are handled by the ANRAN app."
        ),
        "notes": (
            "External cloud camera supervised by Orion. "
            "No RTSP, ONVIF, or local HTTP access detected."
        ),
    }
]


def _camera_payload(camera: Dict[str, Any]) -> Dict[str, Any]:
    return {
        **camera,
        "last_checked": time.time(),
        "capabilities": {
            "local_stream": False,
            "rtsp": False,
            "onvif": False,
            "http_ui": False,
            "vendor_app_live_view": True,
            "vendor_app_ptz": True,
            "vendor_app_motion_alerts": True,
            "vendor_app_playback": True,
            "orion_health_monitoring": True,
        },
        "orion_role": "Supervised external camera",
    }


def get_camera_status() -> Dict[str, Any]:
    devices = [_camera_payload(camera) for camera in CAMERAS]

    return {
        "system": "cameras",
        "summary": {
            "total": len(devices),
            "native_streams": sum(1 for d in devices if d["stream_access"]),
            "external_cloud": sum(
                1 for d in devices if d["integration_type"] == "external_cloud"
            ),
            "online": sum(1 for d in devices if d["health"] == "online"),
            "unknown": sum(1 for d in devices if d["health"] == "unknown"),
            "offline": sum(1 for d in devices if d["health"] == "offline"),
        },
        "devices": devices,
    }
