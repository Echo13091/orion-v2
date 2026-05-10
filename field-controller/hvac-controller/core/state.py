import copy
import json
import threading
import time
from pathlib import Path
from typing import Any

# =====================================================
# FILES / CONSTANTS
# =====================================================
BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / "hvac_state.json"

VALID_MODES = {"off", "cool", "heat", "auto"}
VALID_FAN_MODES = {"auto", "on", "off"}

PERSISTENT_KEYS = {
    "setpoint",
    "mode",
    "system_mode",
    "hvac_mode",
    "fan_mode",
    "stage2_enabled",
}

state_lock = threading.RLock()

hvac_state: dict[str, Any] = {
    "online": False,
    "node_online": False,
    "heartbeat": "offline",
    "health": "offline",

    "last_seen": 0.0,
    "last_heartbeat_seen": 0.0,
    "last_sensor_seen": 0.0,

    "offline_timeout": 20,
    "sensor_stale_timeout": 45,

    "temp": None,
    "temperature": None,
    "current_temp": None,
    "humidity": None,

    "sensor_status": "unknown",
    "sensor_data_valid": False,
    "dht_raw_status": "unknown",

    "mode": "auto",
    "system_mode": "auto",
    "hvac_mode": "auto",
    "hvac_state": "OFFLINE",

    # Commanded/control state from this controller
    "cooling": False,
    "heating": False,
    "fan": False,

    "cooling_active": False,
    "heating_active": False,
    "fan_active": False,
    "fan_on": False,

    # Physical relay feedback from ESP32
    "relay_cool": False,
    "relay_heat": False,
    "relay_fan": False,

    "relay_cool_stage1": False,
    "relay_cool_stage2": False,
    "relay_heat_stage1": False,
    "relay_heat_stage2": False,

    # Commanded stages from this controller
    "cool_stage": 0,
    "heat_stage": 0,

    "cool_stage1": False,
    "cool_stage2": False,
    "heat_stage1": False,
    "heat_stage2": False,

    # Node-reported feedback fields.
    # These are feedback only. They must not re-command equipment.
    "node_cool_stage": 0,
    "node_heat_stage": 0,
    "node_cooling": False,
    "node_heating": False,
    "node_fan": False,

    "setpoint": 72,
    "fan_mode": "auto",

    "stage2_available": False,
    "stage2_enabled": False,

    "last_action": "startup",
    "last_mode_change": 0.0,

    "last_cool_on": 0.0,
    "last_cool_off": 0.0,

    "last_heat_on": 0.0,
    "last_heat_off": 0.0,

    "last_fan_on": 0.0,
    "last_fan_off": 0.0,

    "last_equipment_off": 0.0,

    "fan_post_run_until": 0.0,
    "fan_post_run_remaining": 0,
    "fan_post_run_seconds": 45,

    "changeover_delay": 300,
    "changeover_lockout_remaining": 0,

    "min_on_time": 300,
    "min_off_time": 300,

    "min_cool_on_remaining": 0,
    "min_cool_off_remaining": 0,

    "min_heat_on_remaining": 0,
    "min_heat_off_remaining": 0,

    "control_loop_delay": 1,
    "relay_feedback_timeout": 12,

    "fault": True,
    "fault_code": "NODE_OFFLINE",
    "fault_message": "Node offline",
    "fault_severity": "critical",

    "reported_faults": {},
    "external_alarms": [],
    "alarms": [],

    "last_node_msg_age": None,
    "last_heartbeat_msg_age": None,
    "last_sensor_msg_age": None,
}

# Compatibility for older modules importing `state`.
state = hvac_state


# =====================================================
# TIME
# =====================================================
def now() -> float:
    return time.time()


# =====================================================
# PERSISTENCE
# =====================================================
def persist_state() -> None:
    try:
        with state_lock:
            payload = {
                key: hvac_state[key]
                for key in PERSISTENT_KEYS
                if key in hvac_state
            }

        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    except Exception as exc:
        print(f"STATE SAVE ERROR: {exc}", flush=True)


def _load_persistent_state() -> None:
    if not STATE_FILE.exists():
        return

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)

        if not isinstance(payload, dict):
            return

        with state_lock:
            for key in PERSISTENT_KEYS:
                if key in payload:
                    hvac_state[key] = payload[key]

            _sync_mode_aliases_locked()

    except Exception as exc:
        print(f"STATE LOAD ERROR: {exc}", flush=True)


# =====================================================
# INTERNAL HELPERS
# =====================================================
def _safe_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return fallback


def _node_is_online_locked() -> bool:
    ts = now()
    last_seen = float(hvac_state.get("last_seen") or 0)
    timeout = int(hvac_state.get("offline_timeout") or 20)

    return last_seen > 0 and (ts - last_seen) <= timeout


def _sensor_is_fresh_locked() -> bool:
    ts = now()
    last_sensor_seen = float(hvac_state.get("last_sensor_seen") or 0)
    timeout = int(hvac_state.get("sensor_stale_timeout") or 45)

    return last_sensor_seen > 0 and (ts - last_sensor_seen) <= timeout


def _sync_temperature_aliases_locked(value: Any) -> None:
    hvac_state["temp"] = value
    hvac_state["temperature"] = value
    hvac_state["current_temp"] = value


def _sync_mode_aliases_locked() -> None:
    mode = str(
        hvac_state.get("mode")
        or hvac_state.get("system_mode")
        or hvac_state.get("hvac_mode")
        or "auto"
    ).strip().lower()

    if mode not in VALID_MODES:
        mode = "auto"

    hvac_state["mode"] = mode
    hvac_state["system_mode"] = mode
    hvac_state["hvac_mode"] = mode

    fan_mode = str(hvac_state.get("fan_mode") or "auto").strip().lower()

    if fan_mode in {"enabled", "true", "1"}:
        fan_mode = "on"

    if fan_mode in {"disabled", "false", "0"}:
        fan_mode = "off"

    if fan_mode not in VALID_FAN_MODES:
        fan_mode = "auto"

    hvac_state["fan_mode"] = fan_mode


def _clear_runtime_when_offline_locked() -> None:
    # Offline node means no valid telemetry. Never fake 0.0 values.
    _sync_temperature_aliases_locked(None)

    hvac_state["humidity"] = None
    hvac_state["sensor_status"] = "unknown"
    hvac_state["sensor_data_valid"] = False
    hvac_state["dht_raw_status"] = "unknown"

    hvac_state["cooling"] = False
    hvac_state["heating"] = False
    hvac_state["fan"] = False

    hvac_state["cooling_active"] = False
    hvac_state["heating_active"] = False
    hvac_state["fan_active"] = False
    hvac_state["fan_on"] = False

    hvac_state["relay_cool"] = False
    hvac_state["relay_heat"] = False
    hvac_state["relay_fan"] = False

    hvac_state["relay_cool_stage1"] = False
    hvac_state["relay_cool_stage2"] = False
    hvac_state["relay_heat_stage1"] = False
    hvac_state["relay_heat_stage2"] = False

    hvac_state["cool_stage"] = 0
    hvac_state["heat_stage"] = 0

    hvac_state["cool_stage1"] = False
    hvac_state["cool_stage2"] = False
    hvac_state["heat_stage1"] = False
    hvac_state["heat_stage2"] = False

    hvac_state["node_cool_stage"] = 0
    hvac_state["node_heat_stage"] = 0
    hvac_state["node_cooling"] = False
    hvac_state["node_heating"] = False
    hvac_state["node_fan"] = False

    hvac_state["fan_post_run_until"] = 0.0
    hvac_state["fan_post_run_remaining"] = 0

    hvac_state["hvac_state"] = "OFFLINE"


def _sync_stage_aliases_locked() -> None:
    """
    Sync aliases safely.

    Critical rule:
    - cooling/heating/fan are COMMANDED state.
    - relay_* and node_* are FEEDBACK state.
    - feedback must not re-command equipment.

    This prevents a stale ESP32 relay report from forcing the controller back
    into COOLING/HEATING after the control loop has commanded equipment off.
    """
    relay_cool_stage1 = bool(hvac_state.get("relay_cool_stage1"))
    relay_cool_stage2 = bool(hvac_state.get("relay_cool_stage2"))
    relay_heat_stage1 = bool(hvac_state.get("relay_heat_stage1"))
    relay_heat_stage2 = bool(hvac_state.get("relay_heat_stage2"))

    relay_cool = (
        bool(hvac_state.get("relay_cool"))
        or relay_cool_stage1
        or relay_cool_stage2
    )

    relay_heat = (
        bool(hvac_state.get("relay_heat"))
        or relay_heat_stage1
        or relay_heat_stage2
    )

    relay_fan = bool(hvac_state.get("relay_fan"))

    # Keep relay feedback visible.
    hvac_state["relay_cool"] = relay_cool
    hvac_state["relay_heat"] = relay_heat
    hvac_state["relay_fan"] = relay_fan

    commanded_cool_stage = _safe_int(hvac_state.get("cool_stage"), 0)
    commanded_heat_stage = _safe_int(hvac_state.get("heat_stage"), 0)

    # IMPORTANT:
    # Do not include node_cooling/node_heating/node_fan or relay_* here.
    # Those are feedback only and can be stale briefly.
    cooling_commanded = bool(
        hvac_state.get("cooling_active")
        or commanded_cool_stage >= 1
    )

    heating_commanded = bool(
        hvac_state.get("heating_active")
        or commanded_heat_stage >= 1
    )

    # Never allow both heat and cool to be true in public state.
    if cooling_commanded and heating_commanded:
        last_action = str(hvac_state.get("last_action") or "").lower()
        if last_action.startswith("heat"):
            cooling_commanded = False
        else:
            heating_commanded = False

    cool_stage = commanded_cool_stage if cooling_commanded else 0
    heat_stage = commanded_heat_stage if heating_commanded else 0

    hvac_state["cool_stage"] = cool_stage
    hvac_state["heat_stage"] = heat_stage

    hvac_state["cool_stage1"] = bool(cooling_commanded and cool_stage >= 1)
    hvac_state["cool_stage2"] = bool(cooling_commanded and cool_stage >= 2)

    hvac_state["heat_stage1"] = bool(heating_commanded and heat_stage >= 1)
    hvac_state["heat_stage2"] = bool(heating_commanded and heat_stage >= 2)

    fan_commanded = bool(
        hvac_state.get("fan_active")
        or hvac_state.get("fan_on")
        or cooling_commanded
        or heating_commanded
    )

    hvac_state["cooling"] = cooling_commanded
    hvac_state["heating"] = heating_commanded
    hvac_state["fan"] = fan_commanded

    hvac_state["cooling_active"] = cooling_commanded
    hvac_state["heating_active"] = heating_commanded
    hvac_state["fan_active"] = fan_commanded
    hvac_state["fan_on"] = fan_commanded

    if cooling_commanded:
        hvac_state["hvac_state"] = "COOLING"
    elif heating_commanded:
        hvac_state["hvac_state"] = "HEATING"
    elif fan_commanded:
        fan_until = float(hvac_state.get("fan_post_run_until") or 0)
        if fan_until and now() < fan_until:
            hvac_state["hvac_state"] = "FAN_POST_RUN"
        else:
            hvac_state["hvac_state"] = "FAN"
    else:
        hvac_state["hvac_state"] = "IDLE"


def _sync_timers_locked() -> None:
    ts = now()

    fan_until = float(hvac_state.get("fan_post_run_until") or 0)
    hvac_state["fan_post_run_remaining"] = (
        max(0, int(fan_until - ts))
        if fan_until
        else 0
    )

    if hvac_state.get("cooling"):
        hvac_state["min_cool_on_remaining"] = max(
            0,
            int(
                (
                    float(hvac_state.get("last_cool_on") or 0)
                    + float(hvac_state.get("min_on_time") or 0)
                )
                - ts
            ),
        )
    else:
        hvac_state["min_cool_on_remaining"] = 0

    hvac_state["min_cool_off_remaining"] = max(
        0,
        int(
            (
                float(hvac_state.get("last_cool_off") or 0)
                + float(hvac_state.get("min_off_time") or 0)
            )
            - ts
        ),
    )

    if hvac_state.get("heating"):
        hvac_state["min_heat_on_remaining"] = max(
            0,
            int(
                (
                    float(hvac_state.get("last_heat_on") or 0)
                    + float(hvac_state.get("min_on_time") or 0)
                )
                - ts
            ),
        )
    else:
        hvac_state["min_heat_on_remaining"] = 0

    hvac_state["min_heat_off_remaining"] = max(
        0,
        int(
            (
                float(hvac_state.get("last_heat_off") or 0)
                + float(hvac_state.get("min_off_time") or 0)
            )
            - ts
        ),
    )

    hvac_state["changeover_lockout_remaining"] = max(
        0,
        int(
            (
                float(hvac_state.get("last_mode_change") or 0)
                + float(hvac_state.get("changeover_delay") or 0)
            )
            - ts
        ),
    )


def _build_alarms_locked() -> None:
    alarms = []

    if hvac_state.get("fault"):
        code = hvac_state.get("fault_code") or "FAULT"
        message = hvac_state.get("fault_message") or code
        alarms.append(f"{code}: {message}")

    for code, fault in hvac_state.get("reported_faults", {}).items():
        if not isinstance(fault, dict):
            continue

        if fault.get("active") is False:
            continue

        message = fault.get("message") or code
        item = f"{code}: {message}"

        if item not in alarms:
            alarms.append(item)

    for item in hvac_state.get("external_alarms", []):
        text = str(item)

        if text and text not in alarms:
            alarms.append(text)

    hvac_state["alarms"] = alarms


def _sync_state_locked() -> None:
    ts = now()

    _sync_mode_aliases_locked()

    node_online = _node_is_online_locked()
    sensor_fresh = _sensor_is_fresh_locked()

    hvac_state["node_online"] = node_online
    hvac_state["online"] = node_online
    hvac_state["heartbeat"] = "online" if node_online else "offline"

    hvac_state["last_node_msg_age"] = (
        int(ts - float(hvac_state.get("last_seen") or 0))
        if hvac_state.get("last_seen")
        else None
    )

    hvac_state["last_heartbeat_msg_age"] = (
        int(ts - float(hvac_state.get("last_heartbeat_seen") or 0))
        if hvac_state.get("last_heartbeat_seen")
        else None
    )

    hvac_state["last_sensor_msg_age"] = (
        int(ts - float(hvac_state.get("last_sensor_seen") or 0))
        if hvac_state.get("last_sensor_seen")
        else None
    )

    if not node_online:
        hvac_state["health"] = "offline"
        hvac_state["fault"] = True
        hvac_state["fault_code"] = "NODE_OFFLINE"
        hvac_state["fault_message"] = "Node offline"
        hvac_state["fault_severity"] = "critical"

        _clear_runtime_when_offline_locked()
        _sync_timers_locked()
        _build_alarms_locked()
        return

    _sync_stage_aliases_locked()
    _sync_timers_locked()

    if not sensor_fresh:
        hvac_state["health"] = "fault"
        hvac_state["fault"] = True
        hvac_state["fault_code"] = "SENSOR_STALE"
        hvac_state["fault_message"] = "Sensor data is stale"
        hvac_state["fault_severity"] = "warning"

        _build_alarms_locked()
        return

    active_faults = [
        fault
        for fault in hvac_state.get("reported_faults", {}).values()
        if isinstance(fault, dict) and fault.get("active", True)
    ]

    if active_faults:
        fault = active_faults[0]

        hvac_state["health"] = "fault"
        hvac_state["fault"] = True
        hvac_state["fault_code"] = fault.get("code", "FAULT")
        hvac_state["fault_message"] = fault.get("message", "Fault")
        hvac_state["fault_severity"] = fault.get("severity", "warning")

        _build_alarms_locked()
        return

    hvac_state["health"] = "online"
    hvac_state["fault"] = False
    hvac_state["fault_code"] = ""
    hvac_state["fault_message"] = ""
    hvac_state["fault_severity"] = ""

    _build_alarms_locked()


# =====================================================
# PUBLIC GETTERS
# =====================================================
def get_state() -> dict[str, Any]:
    with state_lock:
        _sync_state_locked()
        return copy.deepcopy(hvac_state)


def get_state_copy() -> dict[str, Any]:
    return get_state()


def get_public_state() -> dict[str, Any]:
    return get_state()


# =====================================================
# PUBLIC MUTATORS
# =====================================================
def update_state(**updates: Any) -> None:
    with state_lock:
        hvac_state.update(updates)

        if "temp" in updates:
            _sync_temperature_aliases_locked(updates.get("temp"))

        elif "temperature" in updates:
            _sync_temperature_aliases_locked(updates.get("temperature"))

        elif "current_temp" in updates:
            _sync_temperature_aliases_locked(updates.get("current_temp"))

        if "mode" in updates:
            hvac_state["system_mode"] = updates.get("mode")
            hvac_state["hvac_mode"] = updates.get("mode")

        if "system_mode" in updates:
            hvac_state["mode"] = updates.get("system_mode")
            hvac_state["hvac_mode"] = updates.get("system_mode")

        if "hvac_mode" in updates:
            hvac_state["mode"] = updates.get("hvac_mode")
            hvac_state["system_mode"] = updates.get("hvac_mode")

        if "cooling" in updates:
            hvac_state["cooling_active"] = bool(updates.get("cooling"))

        if "heating" in updates:
            hvac_state["heating_active"] = bool(updates.get("heating"))

        if "fan" in updates:
            hvac_state["fan_active"] = bool(updates.get("fan"))
            hvac_state["fan_on"] = bool(updates.get("fan"))

        _sync_state_locked()


def mark_seen() -> None:
    ts = now()

    with state_lock:
        hvac_state["last_seen"] = ts
        hvac_state["last_heartbeat_seen"] = ts
        hvac_state["online"] = True
        hvac_state["node_online"] = True
        hvac_state["heartbeat"] = "online"

        _sync_state_locked()


def mark_sensor_seen() -> None:
    ts = now()

    with state_lock:
        hvac_state["last_sensor_seen"] = ts
        hvac_state["sensor_data_valid"] = True

        _sync_state_locked()


def mark_node_offline(reason: str = "Node offline") -> None:
    with state_lock:
        hvac_state["online"] = False
        hvac_state["node_online"] = False
        hvac_state["heartbeat"] = "offline"
        hvac_state["last_action"] = reason
        hvac_state["last_seen"] = 0.0
        hvac_state["last_heartbeat_seen"] = 0.0

        _sync_state_locked()


def set_reported_fault(
    code: str,
    message: str,
    *,
    severity: str = "warning",
    source: str = "mqtt",
    active: bool = True,
) -> None:
    code = str(code or "FAULT").upper()

    with state_lock:
        hvac_state["reported_faults"][code] = {
            "code": code,
            "message": str(message or code),
            "severity": str(severity or "warning"),
            "source": str(source or "mqtt"),
            "active": bool(active),
            "time": now(),
        }

        _sync_state_locked()


def clear_reported_fault(
    code: str | None = None,
    *,
    source: str | None = None,
) -> None:
    with state_lock:
        if code:
            hvac_state["reported_faults"].pop(
                str(code).upper(),
                None,
            )

        elif source:
            hvac_state["reported_faults"] = {
                k: v
                for k, v in hvac_state["reported_faults"].items()
                if v.get("source") != source
            }

        else:
            hvac_state["reported_faults"] = {}

        _sync_state_locked()


def set_alarm_list(alarms: list[str]) -> None:
    with state_lock:
        hvac_state["external_alarms"] = list(alarms or [])
        _sync_state_locked()


def clear_fault() -> None:
    with state_lock:
        hvac_state["fault"] = False
        hvac_state["fault_code"] = ""
        hvac_state["fault_message"] = ""
        hvac_state["fault_severity"] = ""
        hvac_state["reported_faults"] = {}
        hvac_state["external_alarms"] = []
        hvac_state["alarms"] = []

        _sync_state_locked()


def set_setpoint(sp: int) -> None:
    sp = int(sp)

    if sp < 50 or sp > 90:
        raise ValueError("setpoint out of range")

    with state_lock:
        old_sp = _safe_int(hvac_state.get("setpoint"), 72)

        hvac_state["setpoint"] = sp

        if old_sp != sp:
            hvac_state["last_action"] = f"setpoint->{sp}"
        else:
            hvac_state["last_action"] = f"setpoint unchanged->{sp}"

        _sync_state_locked()

    persist_state()


def set_mode(mode: str) -> None:
    mode = str(mode or "").strip().lower()

    if mode not in VALID_MODES:
        raise ValueError("invalid mode")

    with state_lock:
        old_mode = str(
            hvac_state.get("mode")
            or hvac_state.get("system_mode")
            or hvac_state.get("hvac_mode")
            or "auto"
        ).strip().lower()

        hvac_state["mode"] = mode
        hvac_state["system_mode"] = mode
        hvac_state["hvac_mode"] = mode

        # Only reset changeover timing when mode actually changes.
        if old_mode != mode:
            hvac_state["last_mode_change"] = now()
            hvac_state["last_action"] = f"mode->{mode}"
        else:
            hvac_state["last_action"] = f"mode unchanged->{mode}"

        _sync_state_locked()

    persist_state()


def set_hvac_mode(mode: str) -> None:
    set_mode(mode)


def set_system_mode(mode: str) -> None:
    set_mode(mode)


def set_fan_mode(mode: str) -> None:
    mode = str(mode or "").strip().lower()

    if mode in {"enabled", "true", "1"}:
        mode = "on"

    if mode in {"disabled", "false", "0"}:
        mode = "off"

    if mode not in VALID_FAN_MODES:
        raise ValueError("invalid fan mode")

    with state_lock:
        old_mode = str(hvac_state.get("fan_mode") or "auto").strip().lower()

        hvac_state["fan_mode"] = mode

        if old_mode != mode:
            hvac_state["last_action"] = f"fan_mode->{mode}"
        else:
            hvac_state["last_action"] = f"fan_mode unchanged->{mode}"

        _sync_state_locked()

    persist_state()


def set_stage2_enabled(enabled: bool) -> None:
    with state_lock:
        hvac_state["stage2_enabled"] = bool(enabled)
        hvac_state["last_action"] = f"stage2_enabled->{bool(enabled)}"

        _sync_state_locked()

    persist_state()


def set_stage2_available(available: bool) -> None:
    with state_lock:
        hvac_state["stage2_available"] = bool(available)
        hvac_state["last_action"] = f"stage2_available->{bool(available)}"

        _sync_state_locked()


# Load saved mode/setpoint after all helper functions exist.
_load_persistent_state()
