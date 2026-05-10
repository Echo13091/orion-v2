import threading
import time

import paho.mqtt.publish as publish

from core.state import (
    get_state_copy,
    hvac_state,
    set_alarm_list,
    state_lock,
    update_state,
)

MQTT_HOST = "localhost"

DEADBAND = 2.0
STAGE2_OFFSET = 3.0
STAGE2_DELAY_SECONDS = 300

_last_commands = {}


def _now():
    return time.time()


def _as_float(value, fallback=0.0):
    try:
        return float(value)
    except Exception:
        return fallback


def _as_int(value, fallback=0):
    try:
        return int(float(value))
    except Exception:
        return fallback


def mqtt_send(topic, payload, retain=True):
    """
    Publish MQTT commands with de-duplication.

    This prevents repeating:
      COMMAND hvac/fan OFF
      COMMAND hvac/fan OFF
      COMMAND hvac/fan OFF

    every control loop.
    """
    previous = _last_commands.get(topic)

    if previous == payload:
        return

    _last_commands[topic] = payload

    try:
        publish.single(
            topic,
            payload,
            hostname=MQTT_HOST,
            retain=retain,
        )
        print(f"COMMAND {topic} {payload}", flush=True)

    except Exception as exc:
        print(f"MQTT COMMAND ERROR {topic}={payload}: {exc}", flush=True)


def can_turn_on(last_off, min_off):
    return (_now() - _as_float(last_off, 0.0)) >= _as_float(min_off, 0.0)


def can_turn_off(last_on, min_on):
    return (_now() - _as_float(last_on, 0.0)) >= _as_float(min_on, 0.0)


def changeover_ready(state):
    return (_now() - _as_float(state.get("last_mode_change"), 0.0)) >= _as_float(
        state.get("changeover_delay"),
        0.0,
    )


def _set_equipment_state_locked(new_state):
    """
    Update hvac_state and last_mode_change ONLY when the equipment state
    actually changes.

    This fixes the frozen 5-minute lockout problem.

    Bad behavior:
      HEATING -> HEATING -> HEATING
      resets last_mode_change every loop

    Correct behavior:
      HEATING -> HEATING
      does NOT reset last_mode_change

      HEATING -> IDLE
      does reset last_mode_change once

      IDLE -> COOLING
      does reset last_mode_change once
    """
    old_state = str(hvac_state.get("hvac_state") or "IDLE")

    if old_state != new_state:
        hvac_state["last_mode_change"] = _now()

    hvac_state["hvac_state"] = new_state


def _set_display_state_locked(new_state):
    """
    Display-only state change.

    Used for fan-only states so fan post-run does not reset
    heat/cool changeover protection.
    """
    hvac_state["hvac_state"] = new_state


def _publish_cool(stage):
    stage = max(0, min(2, _as_int(stage, 0)))

    mqtt_send("hvac/cool", "ON" if stage >= 1 else "OFF")
    mqtt_send("hvac/cool_stage1", "ON" if stage >= 1 else "OFF")
    mqtt_send("hvac/cool_stage2", "ON" if stage >= 2 else "OFF")


def _publish_heat(stage):
    stage = max(0, min(2, _as_int(stage, 0)))

    mqtt_send("hvac/heat", "ON" if stage >= 1 else "OFF")
    mqtt_send("hvac/heat_stage1", "ON" if stage >= 1 else "OFF")
    mqtt_send("hvac/heat_stage2", "ON" if stage >= 2 else "OFF")


def _publish_fan(enabled):
    mqtt_send("hvac/fan", "ON" if enabled else "OFF")


def _set_fan_state(enabled, *, reason="fan"):
    enabled = bool(enabled)

    with state_lock:
        old = bool(hvac_state.get("fan"))

        hvac_state["fan"] = enabled
        hvac_state["fan_active"] = enabled
        hvac_state["fan_on"] = enabled
        hvac_state["node_fan"] = enabled

        if enabled and not old:
            hvac_state["last_fan_on"] = _now()

        if not enabled and old:
            hvac_state["last_fan_off"] = _now()

        hvac_state["last_action"] = reason

        if enabled:
            if hvac_state.get("cooling"):
                _set_display_state_locked("COOLING")
            elif hvac_state.get("heating"):
                _set_display_state_locked("HEATING")
            elif reason.startswith("fan post"):
                _set_display_state_locked("FAN_POST_RUN")
            else:
                _set_display_state_locked("FAN")
        else:
            if not hvac_state.get("cooling") and not hvac_state.get("heating"):
                _set_display_state_locked("IDLE")

    _publish_fan(enabled)

    if old != enabled:
        print(f"FAN {'ON' if enabled else 'OFF'}", flush=True)


def _start_fan_post_run(seconds):
    seconds = max(0, _as_int(seconds, 45))

    update_state(
        fan_post_run_until=_now() + seconds,
        fan_post_run_remaining=seconds,
        hvac_state="FAN_POST_RUN",
        last_action="fan post-run",
    )


def _clear_fan_post_run():
    update_state(
        fan_post_run_until=0,
        fan_post_run_remaining=0,
    )


def _clear_cooling_state_locked():
    hvac_state["cooling"] = False
    hvac_state["cooling_active"] = False
    hvac_state["node_cooling"] = False

    hvac_state["cool_stage"] = 0
    hvac_state["cool_stage1"] = False
    hvac_state["cool_stage2"] = False
    hvac_state["node_cool_stage"] = 0


def _clear_heating_state_locked():
    hvac_state["heating"] = False
    hvac_state["heating_active"] = False
    hvac_state["node_heating"] = False

    hvac_state["heat_stage"] = 0
    hvac_state["heat_stage1"] = False
    hvac_state["heat_stage2"] = False
    hvac_state["node_heat_stage"] = 0


def set_cooling(enabled):
    enabled = bool(enabled)

    with state_lock:
        old_cooling = bool(hvac_state.get("cooling"))
        old_heating = bool(hvac_state.get("heating"))
        now = _now()

        if enabled:
            if old_heating:
                hvac_state["last_heat_off"] = now
                hvac_state["last_equipment_off"] = now

            _clear_heating_state_locked()

            stage = max(1, _as_int(hvac_state.get("cool_stage"), 1))

            hvac_state["cooling"] = True
            hvac_state["cooling_active"] = True
            hvac_state["node_cooling"] = True

            hvac_state["cool_stage"] = stage
            hvac_state["cool_stage1"] = True
            hvac_state["cool_stage2"] = stage >= 2
            hvac_state["node_cool_stage"] = stage

            if not old_cooling:
                hvac_state["last_cool_on"] = now

            hvac_state["last_action"] = f"cool stage {stage}"
            _set_equipment_state_locked("COOLING")

        else:
            _clear_cooling_state_locked()

            if old_cooling:
                hvac_state["last_cool_off"] = now
                hvac_state["last_equipment_off"] = now
                hvac_state["last_action"] = "cool off"

                if not hvac_state.get("heating"):
                    _set_equipment_state_locked("IDLE")

            else:
                hvac_state["last_action"] = "cool already off"

    if enabled:
        state = get_state_copy()
        stage = max(1, _as_int(state.get("cool_stage"), 1))

        _publish_heat(0)
        _publish_cool(stage)
        _clear_fan_post_run()
        _set_fan_state(True, reason="fan with cooling")

        if not old_cooling:
            print("COOL ON", flush=True)

    else:
        _publish_cool(0)

        if old_cooling:
            _start_fan_post_run(get_state_copy().get("fan_post_run_seconds", 45))
            print("COOL OFF", flush=True)


def set_heating(enabled):
    enabled = bool(enabled)

    with state_lock:
        old_heating = bool(hvac_state.get("heating"))
        old_cooling = bool(hvac_state.get("cooling"))
        now = _now()

        if enabled:
            if old_cooling:
                hvac_state["last_cool_off"] = now
                hvac_state["last_equipment_off"] = now

            _clear_cooling_state_locked()

            stage = max(1, _as_int(hvac_state.get("heat_stage"), 1))

            hvac_state["heating"] = True
            hvac_state["heating_active"] = True
            hvac_state["node_heating"] = True

            hvac_state["heat_stage"] = stage
            hvac_state["heat_stage1"] = True
            hvac_state["heat_stage2"] = stage >= 2
            hvac_state["node_heat_stage"] = stage

            if not old_heating:
                hvac_state["last_heat_on"] = now

            hvac_state["last_action"] = f"heat stage {stage}"
            _set_equipment_state_locked("HEATING")

        else:
            _clear_heating_state_locked()

            if old_heating:
                hvac_state["last_heat_off"] = now
                hvac_state["last_equipment_off"] = now
                hvac_state["last_action"] = "heat off"

                if not hvac_state.get("cooling"):
                    _set_equipment_state_locked("IDLE")

            else:
                hvac_state["last_action"] = "heat already off"

    if enabled:
        state = get_state_copy()
        stage = max(1, _as_int(state.get("heat_stage"), 1))

        _publish_cool(0)
        _publish_heat(stage)
        _clear_fan_post_run()
        _set_fan_state(True, reason="fan with heating")

        if not old_heating:
            print("HEAT ON", flush=True)

    else:
        _publish_heat(0)

        if old_heating:
            _start_fan_post_run(get_state_copy().get("fan_post_run_seconds", 45))
            print("HEAT OFF", flush=True)


def _set_cool_stage(stage):
    stage = max(0, min(2, _as_int(stage, 0)))

    with state_lock:
        old_stage = _as_int(hvac_state.get("cool_stage"), 0)
        old_cooling = bool(hvac_state.get("cooling"))
        old_heating = bool(hvac_state.get("heating"))
        now = _now()

        if stage <= 0:
            _clear_cooling_state_locked()
            hvac_state["last_action"] = "cool stage 0"

            if old_cooling:
                hvac_state["last_cool_off"] = now
                hvac_state["last_equipment_off"] = now

            if not hvac_state.get("heating"):
                _set_equipment_state_locked("IDLE")

        else:
            if old_heating:
                hvac_state["last_heat_off"] = now
                hvac_state["last_equipment_off"] = now

            _clear_heating_state_locked()

            hvac_state["cooling"] = True
            hvac_state["cooling_active"] = True
            hvac_state["node_cooling"] = True

            hvac_state["cool_stage"] = stage
            hvac_state["cool_stage1"] = stage >= 1
            hvac_state["cool_stage2"] = stage >= 2
            hvac_state["node_cool_stage"] = stage

            if not old_cooling:
                hvac_state["last_cool_on"] = now

            hvac_state["last_action"] = f"cool stage {stage}"
            _set_equipment_state_locked("COOLING")

    if old_stage != stage:
        print(f"COOL STAGE {stage}", flush=True)

    _publish_heat(0)
    _publish_cool(stage)

    if stage >= 1:
        _clear_fan_post_run()
        _set_fan_state(True, reason="fan with cooling")


def _set_heat_stage(stage):
    stage = max(0, min(2, _as_int(stage, 0)))

    with state_lock:
        old_stage = _as_int(hvac_state.get("heat_stage"), 0)
        old_heating = bool(hvac_state.get("heating"))
        old_cooling = bool(hvac_state.get("cooling"))
        now = _now()

        if stage <= 0:
            _clear_heating_state_locked()
            hvac_state["last_action"] = "heat stage 0"

            if old_heating:
                hvac_state["last_heat_off"] = now
                hvac_state["last_equipment_off"] = now

            if not hvac_state.get("cooling"):
                _set_equipment_state_locked("IDLE")

        else:
            if old_cooling:
                hvac_state["last_cool_off"] = now
                hvac_state["last_equipment_off"] = now

            _clear_cooling_state_locked()

            hvac_state["heating"] = True
            hvac_state["heating_active"] = True
            hvac_state["node_heating"] = True

            hvac_state["heat_stage"] = stage
            hvac_state["heat_stage1"] = stage >= 1
            hvac_state["heat_stage2"] = stage >= 2
            hvac_state["node_heat_stage"] = stage

            if not old_heating:
                hvac_state["last_heat_on"] = now

            hvac_state["last_action"] = f"heat stage {stage}"
            _set_equipment_state_locked("HEATING")

    if old_stage != stage:
        print(f"HEAT STAGE {stage}", flush=True)

    _publish_cool(0)
    _publish_heat(stage)

    if stage >= 1:
        _clear_fan_post_run()
        _set_fan_state(True, reason="fan with heating")


def _stage2_allowed(state):
    return bool(
        state.get("stage2_enabled")
        or state.get("stage2_available")
    )


def _cool_stage2_needed(state):
    temp = state.get("temp")
    sp = state.get("setpoint")

    if temp is None or sp is None:
        return False

    temp = float(temp)
    sp = float(sp)

    run_seconds = _now() - _as_float(state.get("last_cool_on"), 0.0)

    return (
        temp >= sp + STAGE2_OFFSET
        or (
            run_seconds >= STAGE2_DELAY_SECONDS
            and temp > sp + DEADBAND
        )
    )


def _heat_stage2_needed(state):
    temp = state.get("temp")
    sp = state.get("setpoint")

    if temp is None or sp is None:
        return False

    temp = float(temp)
    sp = float(sp)

    run_seconds = _now() - _as_float(state.get("last_heat_on"), 0.0)

    return (
        temp <= sp - STAGE2_OFFSET
        or (
            run_seconds >= STAGE2_DELAY_SECONDS
            and temp < sp - DEADBAND
        )
    )


def _update_staging(state):
    if not _stage2_allowed(state):
        if state.get("cooling") and _as_int(state.get("cool_stage"), 0) > 1:
            _set_cool_stage(1)

        if state.get("heating") and _as_int(state.get("heat_stage"), 0) > 1:
            _set_heat_stage(1)

        return

    if state.get("cooling"):
        stage = 2 if _cool_stage2_needed(state) else 1
        _set_cool_stage(stage)

    elif state.get("heating"):
        stage = 2 if _heat_stage2_needed(state) else 1
        _set_heat_stage(stage)


def _reconcile_feedback_state(state):
    updates = {}

    cooling_command_gone = (
        not bool(state.get("relay_cool"))
        and _as_int(state.get("cool_stage"), 0) == 0
        and not bool(state.get("cool_stage1"))
        and not bool(state.get("cool_stage2"))
    )

    heating_command_gone = (
        not bool(state.get("relay_heat"))
        and _as_int(state.get("heat_stage"), 0) == 0
        and not bool(state.get("heat_stage1"))
        and not bool(state.get("heat_stage2"))
    )

    if state.get("cooling") and cooling_command_gone:
        updates.update(
            {
                "cooling": False,
                "cooling_active": False,
                "node_cooling": False,
                "node_cool_stage": 0,
            }
        )

    if state.get("heating") and heating_command_gone:
        updates.update(
            {
                "heating": False,
                "heating_active": False,
                "node_heating": False,
                "node_heat_stage": 0,
            }
        )

    if updates:
        if state.get("fan") or state.get("relay_fan"):
            updates["hvac_state"] = "FAN_POST_RUN"
            updates["last_action"] = "fan post-run"
        else:
            updates["hvac_state"] = "IDLE"
            updates["last_action"] = "idle"

        update_state(**updates)


def _handle_fan_post_run(state):
    fan_mode = str(state.get("fan_mode") or "auto").lower()
    now = _now()

    if fan_mode == "on":
        _set_fan_state(True, reason="manual fan on")
        return

    if fan_mode == "off":
        if not state.get("cooling") and not state.get("heating"):
            _clear_fan_post_run()
            _set_fan_state(False, reason="manual fan off")
        return

    if state.get("cooling") or state.get("heating"):
        _clear_fan_post_run()
        _set_fan_state(True, reason="equipment fan")
        return

    post_until = float(state.get("fan_post_run_until") or 0)

    if post_until and now < post_until:
        _set_fan_state(True, reason="fan post-run")

        current = get_state_copy()

        if current.get("cooling"):
            update_state(
                hvac_state="COOLING",
                last_action="fan with cooling",
            )

        elif current.get("heating"):
            update_state(
                hvac_state="HEATING",
                last_action="fan with heating",
            )

        else:
            update_state(
                hvac_state="FAN_POST_RUN",
                last_action="fan post-run",
            )

    else:
        _clear_fan_post_run()
        _set_fan_state(False, reason="fan auto idle")

        current = get_state_copy()

        if not current.get("cooling") and not current.get("heating"):
            update_state(
                hvac_state="IDLE",
                last_action="idle",
            )


def _build_alarms(state):
    alarms = []

    if not state.get("node_online"):
        alarms.append("NODE_OFFLINE: HVAC ESP32 node offline")

    if state.get("fault"):
        code = state.get("fault_code") or "FAULT"
        message = state.get("fault_message") or code
        item = f"{code}: {message}"

        if item not in alarms:
            alarms.append(item)

    if str(state.get("sensor_status") or "").lower() in {
        "fault",
        "bad",
        "error",
        "offline",
        "failed",
        "fail",
    }:
        alarms.append("DHT_SENSOR_FAULT: DHT sensor reported fault")

    if state.get("node_online") and state.get("last_sensor_seen"):
        age = _now() - float(state.get("last_sensor_seen") or 0)

        if age > float(state.get("sensor_stale_timeout") or 45):
            alarms.append("SENSOR_STALE: Sensor data is stale")

    relay_timeout = float(state.get("relay_feedback_timeout") or 12)
    age = _now() - float(state.get("last_seen") or 0)

    def relay_alarm(command, relay, name):
        if command and not relay and age > relay_timeout:
            alarms.append(
                f"{name}_RELAY_MISMATCH: {name.title()} command active but relay feedback is OFF"
            )

        if not command and relay and age > relay_timeout:
            alarms.append(
                f"{name}_RELAY_STUCK: {name.title()} command is OFF but relay feedback is ON"
            )

    if state.get("node_online"):
        relay_alarm(bool(state.get("cooling")), bool(state.get("relay_cool")), "COOL")
        relay_alarm(bool(state.get("heating")), bool(state.get("relay_heat")), "HEAT")
        relay_alarm(bool(state.get("fan")), bool(state.get("relay_fan")), "FAN")

    set_alarm_list(alarms)


def _force_idle(reason):
    _publish_cool(0)
    _publish_heat(0)
    _publish_fan(False)

    with state_lock:
        _clear_cooling_state_locked()
        _clear_heating_state_locked()

        hvac_state["fan"] = False
        hvac_state["fan_active"] = False
        hvac_state["fan_on"] = False
        hvac_state["node_fan"] = False

        hvac_state["fan_post_run_until"] = 0
        hvac_state["fan_post_run_remaining"] = 0

        _set_equipment_state_locked("LOCKOUT")
        hvac_state["last_action"] = reason


def hvac_loop():
    while True:
        try:
            state = get_state_copy()
            delay = float(state.get("control_loop_delay") or 1)

            if not bool(state.get("node_online")):
                _force_idle("node offline lockout")
                _build_alarms(get_state_copy())
                time.sleep(delay)
                continue

            _reconcile_feedback_state(state)

            state = get_state_copy()
            temp = state.get("temp")
            sp = state.get("setpoint")
            mode = str(state.get("mode") or "auto").lower()

            if temp is None or sp is None:
                _build_alarms(state)
                time.sleep(delay)
                continue

            temp = float(temp)
            sp = float(sp)

            if str(state.get("last_action") or "").startswith("setpoint->"):
                print(
                    f"CONTROL LOOP setpoint={sp} temp={temp} mode={mode}",
                    flush=True,
                )

            if mode == "off":
                set_cooling(False)
                set_heating(False)
                update_state(hvac_state="IDLE", last_action="mode off")

            elif mode == "cool":
                set_heating(False)
                state = get_state_copy()

                if temp > sp + DEADBAND:
                    if can_turn_on(state.get("last_cool_off"), state.get("min_off_time")):
                        set_cooling(True)

                elif temp <= sp:
                    if can_turn_off(state.get("last_cool_on"), state.get("min_on_time")):
                        set_cooling(False)

            elif mode == "heat":
                set_cooling(False)
                state = get_state_copy()

                if temp < sp - DEADBAND:
                    if can_turn_on(state.get("last_heat_off"), state.get("min_off_time")):
                        set_heating(True)

                elif temp >= sp:
                    if can_turn_off(state.get("last_heat_on"), state.get("min_on_time")):
                        set_heating(False)

            elif mode == "auto":
                state = get_state_copy()

                if temp > sp + DEADBAND:
                    if state.get("heating"):
                        if can_turn_off(state.get("last_heat_on"), state.get("min_on_time")):
                            set_heating(False)

                    state = get_state_copy()

                    if (
                        not state.get("heating")
                        and changeover_ready(state)
                        and can_turn_on(state.get("last_cool_off"), state.get("min_off_time"))
                    ):
                        set_cooling(True)

                elif temp < sp - DEADBAND:
                    if state.get("cooling"):
                        if can_turn_off(state.get("last_cool_on"), state.get("min_on_time")):
                            set_cooling(False)

                    state = get_state_copy()

                    if (
                        not state.get("cooling")
                        and changeover_ready(state)
                        and can_turn_on(state.get("last_heat_off"), state.get("min_off_time"))
                    ):
                        set_heating(True)

                else:
                    state = get_state_copy()

                    if state.get("cooling"):
                        if can_turn_off(state.get("last_cool_on"), state.get("min_on_time")):
                            set_cooling(False)

                    if state.get("heating"):
                        if can_turn_off(state.get("last_heat_on"), state.get("min_on_time")):
                            set_heating(False)

                    state = get_state_copy()

                    if not state.get("cooling") and not state.get("heating"):
                        update_state(hvac_state="IDLE", last_action="idle")

            state = get_state_copy()

            _update_staging(state)
            _reconcile_feedback_state(get_state_copy())
            _handle_fan_post_run(get_state_copy())
            _build_alarms(get_state_copy())

            time.sleep(delay)

        except Exception as exc:
            print(f"HVAC LOOP ERROR: {exc}", flush=True)
            time.sleep(1)


def start_logic():
    threading.Thread(
        target=hvac_loop,
        daemon=True,
    ).start()
