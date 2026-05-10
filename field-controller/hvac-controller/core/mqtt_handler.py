import json
import time
from typing import Any

from core.state import (
    clear_reported_fault,
    get_state_copy,
    set_reported_fault,
    update_state,
)

MIN_VALID_TEMP_F = 35.0
MAX_VALID_TEMP_F = 120.0
MIN_VALID_HUMIDITY = 1.0
MAX_VALID_HUMIDITY = 100.0


def _json_payload(payload: str) -> Any:
    try:
        return json.loads(payload)
    except Exception:
        return None


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value

    if value is None:
        return default

    if isinstance(value, (int, float)):
        return value != 0

    text = str(value).strip().lower()

    if text in {"1", "true", "yes", "y", "on", "online", "ok", "active"}:
        return True

    if text in {"0", "false", "no", "n", "off", "offline", "clear", "normal", "none"}:
        return False

    return default


def _safe_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return fallback


def _safe_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return fallback


def _sensor_values_valid(temp: Any, humidity: Any) -> bool:
    try:
        temp_f = float(temp)
        humidity_value = float(humidity)
    except Exception:
        return False

    if temp_f < MIN_VALID_TEMP_F or temp_f > MAX_VALID_TEMP_F:
        return False

    if humidity_value < MIN_VALID_HUMIDITY or humidity_value > MAX_VALID_HUMIDITY:
        return False

    return True


def _is_live_only_topic(topic: str) -> bool:
    if topic in {
        "hvac/status",
        "hvac/heartbeat",
        "hvac/node",
        "hvac/dht_status",
    }:
        return True

    if topic.startswith("hvac/relay/"):
        return True

    if topic.startswith("hvac/status/"):
        return True

    return False


def _handle_fault_payload(payload: str, topic_code: str = "") -> None:
    data = _json_payload(payload)

    if isinstance(data, dict):
        code = str(
            data.get("code")
            or data.get("fault_code")
            or topic_code
            or "HVAC_FAULT"
        ).strip().upper()

        clear_requested = (
            data.get("clear") is True
            or data.get("active") is False
            or str(data.get("action", "")).lower() in {"clear", "reset", "resolved"}
        )

        if clear_requested:
            clear_reported_fault(code)
            print(f"FAULT CLEARED: {code}")
            return

        message = str(
            data.get("message")
            or data.get("fault_message")
            or code
        ).strip()

        severity = str(
            data.get("severity")
            or data.get("fault_severity")
            or "warning"
        ).strip().lower()

        source = str(
            data.get("source")
            or "mqtt"
        ).strip()

        set_reported_fault(
            code,
            message,
            severity=severity,
            source=source,
            active=True,
        )

        print(f"FAULT ADDED: {code}: {message}")
        return

    text = str(payload or "").strip()

    if text.lower() in {"clear", "ok", "normal", "false", "0", "off"}:
        clear_reported_fault(topic_code or None)
        print(f"FAULT CLEARED: {topic_code or 'all'}")
        return

    code = str(topic_code or text or "HVAC_FAULT").strip().upper()

    set_reported_fault(
        code,
        text or code,
        severity="warning",
        source="mqtt",
        active=True,
    )

    print(f"FAULT ADDED: {code}")


def _update_node_reported_state_from_status(data, updates):
    if "node_cooling" in data:
        updates["node_cooling"] = _as_bool(data.get("node_cooling"))

    if "node_heating" in data:
        updates["node_heating"] = _as_bool(data.get("node_heating"))

    if "node_fan" in data:
        updates["node_fan"] = _as_bool(data.get("node_fan"))

    if "node_cool_stage" in data:
        updates["node_cool_stage"] = _safe_int(data.get("node_cool_stage"), 0)

    if "node_heat_stage" in data:
        updates["node_heat_stage"] = _safe_int(data.get("node_heat_stage"), 0)

    # Backward compatibility.
    # These are node-reported states, not backend commands.
    if "cooling" in data:
        updates["node_cooling"] = _as_bool(data.get("cooling"))

    if "heating" in data:
        updates["node_heating"] = _as_bool(data.get("heating"))

    if "fan" in data:
        updates["node_fan"] = _as_bool(data.get("fan"))

    if "cool_stage" in data:
        updates["node_cool_stage"] = _safe_int(data.get("cool_stage"), 0)

    if "heat_stage" in data:
        updates["node_heat_stage"] = _safe_int(data.get("heat_stage"), 0)


def _update_relay_feedback_from_status(data, updates):
    stage2_seen = False

    if "relay_cool" in data:
        relay_cool = _as_bool(data.get("relay_cool"))
        updates["relay_cool"] = relay_cool
        updates["relay_cool_stage1"] = relay_cool

    if "relay_heat" in data:
        relay_heat = _as_bool(data.get("relay_heat"))
        updates["relay_heat"] = relay_heat
        updates["relay_heat_stage1"] = relay_heat

    if "relay_fan" in data:
        updates["relay_fan"] = _as_bool(data.get("relay_fan"))

    if "relay_cool_stage1" in data:
        relay = _as_bool(data.get("relay_cool_stage1"))
        updates["relay_cool_stage1"] = relay
        updates["relay_cool"] = relay or bool(updates.get("relay_cool_stage2", False))

    if "relay_cool_stage2" in data:
        relay = _as_bool(data.get("relay_cool_stage2"))
        updates["relay_cool_stage2"] = relay
        updates["relay_cool"] = bool(updates.get("relay_cool_stage1", False)) or relay
        stage2_seen = True

    if "relay_heat_stage1" in data:
        relay = _as_bool(data.get("relay_heat_stage1"))
        updates["relay_heat_stage1"] = relay
        updates["relay_heat"] = relay or bool(updates.get("relay_heat_stage2", False))

    if "relay_heat_stage2" in data:
        relay = _as_bool(data.get("relay_heat_stage2"))
        updates["relay_heat_stage2"] = relay
        updates["relay_heat"] = bool(updates.get("relay_heat_stage1", False)) or relay
        stage2_seen = True

    if stage2_seen:
        updates["stage2_available"] = True


def handle_hvac(topic, payload, retained=False):
    now = time.time()

    topic = str(topic or "").strip()
    payload = str(payload or "")

    if retained and _is_live_only_topic(topic):
        print(f"IGNORED RETAINED MQTT {topic} -> {payload}")
        return

    if topic == "hvac/status":
        data = _json_payload(payload)

        if not isinstance(data, dict):
            print(f"Invalid hvac/status payload: {payload}")

            set_reported_fault(
                "INVALID_STATUS_PAYLOAD",
                "Invalid JSON received on hvac/status",
                severity="warning",
                source="mqtt",
            )

            return

        clear_reported_fault("INVALID_STATUS_PAYLOAD")

        updates = {
            "last_seen": now,
            "node_online": True,
            "heartbeat": "online",
        }

        has_temp = "temp" in data or "temperature" in data
        has_humidity = "humidity" in data

        raw_temp = data.get("temp", data.get("temperature"))
        raw_humidity = data.get("humidity")

        if has_temp and has_humidity and _sensor_values_valid(raw_temp, raw_humidity):
            updates["temp"] = _safe_float(raw_temp, 0.0)
            updates["humidity"] = _safe_float(raw_humidity, 0.0)
            updates["last_sensor_seen"] = now
            updates["sensor_data_valid"] = True
            updates["sensor_status"] = "ok"

            clear_reported_fault("DHT_SENSOR_FAULT")
            clear_reported_fault("INVALID_SENSOR_READING")

        elif has_temp or has_humidity:
            updates["sensor_data_valid"] = False
            updates["sensor_status"] = "fault"

            set_reported_fault(
                "INVALID_SENSOR_READING",
                f"Invalid sensor reading temp={raw_temp} humidity={raw_humidity}",
                severity="critical",
                source="sensor",
                active=True,
            )

        sensor_status = str(data.get("sensor_status", "")).lower().strip()

        if sensor_status in {"fault", "bad", "error", "offline", "failed", "fail"}:
            updates["sensor_status"] = "fault"
            updates["sensor_data_valid"] = False

            set_reported_fault(
                "DHT_SENSOR_FAULT",
                "DHT sensor reported fault",
                severity="critical",
                source="sensor",
            )

        _update_node_reported_state_from_status(data, updates)
        _update_relay_feedback_from_status(data, updates)

        update_state(**updates)

    elif topic == "hvac/heartbeat":
        heartbeat = payload.strip().lower() or "online"

        if heartbeat in {"offline", "down", "dead"}:
            update_state(
                heartbeat="offline",
                node_online=False,
            )
            return

        update_state(
            last_seen=now,
            last_heartbeat_seen=now,
            node_online=True,
            heartbeat=heartbeat,
        )

    elif topic == "hvac/node":
        node_status = payload.strip().lower() or "unknown"

        if node_status == "online":
            update_state(
                node_online=True,
                last_seen=now,
                heartbeat="online",
            )

        elif node_status == "offline":
            state = get_state_copy()
            last_seen = float(state.get("last_seen") or 0)
            timeout = int(state.get("offline_timeout") or 20)

            if not last_seen or (now - last_seen) > timeout:
                update_state(
                    node_online=False,
                    heartbeat="offline",
                )

        else:
            update_state(
                heartbeat=node_status,
            )

    elif topic == "hvac/dht_status":
        raw_status = payload.strip().lower() or "unknown"

        updates = {
            "dht_raw_status": raw_status,
            "last_seen": now,
            "node_online": True,
            "heartbeat": "online",
        }

        if raw_status in {"fault", "bad", "error", "offline", "failed", "fail"}:
            updates["sensor_status"] = "fault"
            updates["sensor_data_valid"] = False

            set_reported_fault(
                "DHT_SENSOR_FAULT",
                "DHT sensor reported fault",
                severity="critical",
                source="sensor",
            )

        update_state(**updates)

    elif topic == "hvac/relay/cool":
        relay = _as_bool(payload)

        update_state(
            relay_cool=relay,
            relay_cool_stage1=relay,
            last_seen=now,
            node_online=True,
            heartbeat="online",
        )

    elif topic == "hvac/relay/heat":
        relay = _as_bool(payload)

        update_state(
            relay_heat=relay,
            relay_heat_stage1=relay,
            last_seen=now,
            node_online=True,
            heartbeat="online",
        )

    elif topic == "hvac/relay/fan":
        update_state(
            relay_fan=_as_bool(payload),
            last_seen=now,
            node_online=True,
            heartbeat="online",
        )

    elif topic == "hvac/relay/cool_stage1":
        relay = _as_bool(payload)
        state = get_state_copy()

        update_state(
            relay_cool_stage1=relay,
            relay_cool=(relay or bool(state.get("relay_cool_stage2"))),
            last_seen=now,
            node_online=True,
            heartbeat="online",
        )

    elif topic == "hvac/relay/cool_stage2":
        relay = _as_bool(payload)
        state = get_state_copy()

        update_state(
            relay_cool_stage2=relay,
            relay_cool=(bool(state.get("relay_cool_stage1")) or relay),
            stage2_available=True,
            last_seen=now,
            node_online=True,
            heartbeat="online",
        )

    elif topic == "hvac/relay/heat_stage1":
        relay = _as_bool(payload)
        state = get_state_copy()

        update_state(
            relay_heat_stage1=relay,
            relay_heat=(relay or bool(state.get("relay_heat_stage2"))),
            last_seen=now,
            node_online=True,
            heartbeat="online",
        )

    elif topic == "hvac/relay/heat_stage2":
        relay = _as_bool(payload)
        state = get_state_copy()

        update_state(
            relay_heat_stage2=relay,
            relay_heat=(bool(state.get("relay_heat_stage1")) or relay),
            stage2_available=True,
            last_seen=now,
            node_online=True,
            heartbeat="online",
        )

    elif topic == "hvac/fault":
        _handle_fault_payload(payload)

    elif topic.startswith("hvac/fault/"):
        code = topic.split("/", 2)[2].strip().replace("/", "_")
        _handle_fault_payload(payload, topic_code=code)

    elif topic in {
        "hvac/cool",
        "hvac/heat",
        "hvac/fan",
        "hvac/cool_stage1",
        "hvac/cool_stage2",
        "hvac/heat_stage1",
        "hvac/heat_stage2",
        "hvac/state",
        "hvac/state/cool",
        "hvac/state/heat",
        "hvac/state/fan",
    }:
        pass

    else:
        pass
