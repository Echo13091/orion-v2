from pathlib import Path

from flask import Flask
import paho.mqtt.client as mqtt

from core.mqtt_handler import handle_hvac
from core.logic import start_logic
from web.routes import hvac_bp

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"

app = Flask(__name__, template_folder=str(TEMPLATE_DIR))
app.register_blueprint(hvac_bp)


def on_connect(client, userdata, flags, rc):
    print(f"MQTT connected with rc={rc}")

    if rc == 0:
        client.subscribe("hvac/#")
    else:
        print(f"MQTT connection failed rc={rc}")


def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode()
    except Exception:
        payload = ""

    retained = bool(getattr(msg, "retain", False))

    handle_hvac(
        msg.topic,
        payload,
        retained=retained,
    )


client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect("localhost", 1883)
client.loop_start()

start_logic()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
