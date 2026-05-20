import socket
import subprocess
import time
from typing import Dict, Any, List


CAMERAS = [
    {
        "id": "anran_front_yard",
        "name": "Front Yard Solar Camera",
        "vendor": "ANRAN",
        "model": "Q3/Q3 Pro Solar PTZ",
        "ip": "192.168.50.17",
        "integration_type": "external_cloud",
        "managed_by": "ANRAN App",
        "location": "Front Yard",
        "stream_access": False,
        "ptz_control": "vendor_app",
        "notes": "Closed vendor camera. Local ports are filtered. Video, PTZ, motion events, and playback are handled by ANRAN app.",
    }
]


def _tcp_probe(ip: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False


def _host_probe(ip: str, timeout_seconds: int = 6) -> Dict[str, Any]:
    """
    For closed IoT cameras, ping may fail and ports may be filtered.
    nmap -Pn can still confirm the host exists, but it can be slow.
    This probe is intentionally lightweight.
    """

    common_ports = [80, 443, 554, 8080, 8554, 3702]
    open_ports: List[int] = []

    for port in common_ports:
        if _tcp_probe(ip, port):
            open_ports.append(port)

    if open_ports:
        return {
            "reachable": True,
            "health": "online",
            "probe_method": "tcp_port",
            "open_ports": open_ports,
            "local_access": True,
            "message": "Camera exposes local services.",
        }

    # Try a very short ping. Many cameras block this, so failure does not mean offline.
    try:
        ping = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout_seconds), ip],
            capture_output=True,
            text=True,
            timeout=timeout_seconds + 2,
        )

        if ping.returncode == 0:
            return {
                "reachable": True,
                "health": "online",
                "probe_method": "ping",
                "open_ports": [],
                "local_access": False,
                "message": "Camera responded to ping but exposes no local services.",
            }
    except Exception:
        pass

    # For this ANRAN camera, filtered ports are expected.
    return {
        "reachable": None,
        "health": "unknown",
        "probe_method": "tcp_ping_fallback",
        "open_ports": [],
        "local_access": False,
        "message": "No local services detected. Device may be sleeping, blocking LAN probes, or cloud-managed only.",
    }


def get_camera_status() -> Dict[str, Any]:
    now = time.time()
    devices = []

    for camera in CAMERAS:
        probe = _host_probe(camera["ip"])

        devices.append(
            {
                **camera,
                **probe,
                "last_checked": now,
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
        )

    return {
        "system": "cameras",
        "summary": {
            "total": len(devices),
            "native_streams": sum(1 for d in devices if d["stream_access"]),
            "external_cloud": sum(1 for d in devices if d["integration_type"] == "external_cloud"),
            "online": sum(1 for d in devices if d["health"] == "online"),
            "unknown": sum(1 for d in devices if d["health"] == "unknown"),
            "offline": sum(1 for d in devices if d["health"] == "offline"),
        },
        "devices": devices,
    }
