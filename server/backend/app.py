import os
from threading import Thread

from flask import Flask, jsonify, request
from flask_cors import CORS

from routes.thermostat_routes import thermostat_bp
from routes.cameras import cameras_bp
from routes.events import events_bp

from api.chat import register_chat
from api.control import register_control
from api.sessions import register_sessions
from api.system import register_system
from api.vision import register_vision

from ai.loop import ai_loop
from ai.llm import warm_model


_BACKGROUND_STARTED = False


def _cors_origins() -> list[str]:
    raw = os.getenv(
        "ORION_CORS_ORIGINS",
        "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,http://127.0.0.1:3001",
    )
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def _control_token_configured() -> bool:
    return bool(os.getenv("ORION_CONTROL_TOKEN", "").strip())


def _valid_control_token() -> bool:
    expected = os.getenv("ORION_CONTROL_TOKEN", "").strip()

    if not expected:
        return True

    provided = (
        request.headers.get("X-Orion-Control-Token", "")
        or request.headers.get("Authorization", "").replace("Bearer ", "", 1)
    ).strip()

    return provided == expected


app = Flask(__name__)

CORS(
    app,
    origins=_cors_origins(),
    expose_headers=["X-Session-ID"],
)


# =====================================================
# BASIC SAFETY BOUNDARY
# =====================================================
@app.before_request
def require_control_token_for_hardware_posts():
    """
    Optional local safety gate.

    If ORION_CONTROL_TOKEN is set, POST requests to /v1/control/*
    must include either:

      X-Orion-Control-Token: <token>

    or:

      Authorization: Bearer <token>

    If ORION_CONTROL_TOKEN is unset, Orion keeps current LAN-dev behavior.
    """
    if request.method == "OPTIONS":
        return None

    if request.method != "POST":
        return None

    if not request.path.startswith("/v1/control/"):
        return None

    if not _control_token_configured():
        return None

    if _valid_control_token():
        return None

    return jsonify(
        {
            "ok": False,
            "error": "Control token required for hardware-changing requests.",
        }
    ), 401


# =====================================================
# HEALTH / VERSION ROUTES
# =====================================================
@app.get("/v1/health")
def health():
    return jsonify(
        {
            "ok": True,
            "service": "orion-backend",
            "status": "healthy",
        }
    )


@app.get("/v1/readiness")
def readiness():
    return jsonify(
        {
            "ok": True,
            "service": "orion-backend",
            "ready": True,
        }
    )


@app.get("/v1/version")
def version():
    return jsonify(
        {
            "ok": True,
            "service": "orion-backend",
            "version": os.getenv("ORION_VERSION", "dev"),
            "environment": os.getenv("ORION_ENV", "local"),
        }
    )


# =====================================================
# BLUEPRINT ROUTES
# =====================================================
app.register_blueprint(thermostat_bp)
app.register_blueprint(cameras_bp)
app.register_blueprint(events_bp)


# =====================================================
# API ROUTES
# =====================================================
register_chat(app)
register_sessions(app)
register_system(app)
register_control(app)
register_vision(app)


def start_ai_loop():
    print("[AI] Starting background loop...")
    ai_loop()


def startup():
    print("[SYSTEM] Booting Orion...")

    print("[LLM] Edge mode: model warmup is optional")
    warm_model("default")
    warm_model("code")

    print("[SYSTEM] Startup complete")


def start_background_services_once():
    """
    Starts Orion background services for both:
    - python app.py
    - gunicorn app:app

    Set ORION_DISABLE_STARTUP=1 for CI/import-only checks.
    """
    global _BACKGROUND_STARTED

    if _BACKGROUND_STARTED:
        return

    if os.getenv("ORION_DISABLE_STARTUP", "0").strip().lower() in {"1", "true", "yes", "on"}:
        return

    _BACKGROUND_STARTED = True

    startup()
    Thread(target=start_ai_loop, daemon=True).start()


start_background_services_once()


if __name__ == "__main__":
    print("[WEB] Starting Flask server...")
    app.run(host="0.0.0.0", port=5001)
