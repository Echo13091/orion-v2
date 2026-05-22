from threading import Thread

from flask import Flask
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


app = Flask(__name__)

CORS(
    app,
    expose_headers=["X-Session-ID"],
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


if __name__ == "__main__":
    startup()

    Thread(target=start_ai_loop, daemon=True).start()

    print("[WEB] Starting Flask server...")
    app.run(host="0.0.0.0", port=5001)
