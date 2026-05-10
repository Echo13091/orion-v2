from flask import jsonify, redirect, render_template, request, url_for

from core.scheduler import emergency_stop, start_manual_zone_async, start_program_async
from core.state import DAY_LABELS, ZONE_COUNT, get_public_state
from core.storage import (
    DEFAULT_PROGRAM,
    build_upcoming_timeline,
    compute_schedule,
    delete_program,
    load_program,
    next_run,
    save_program,
)


def format_remaining(seconds):
    seconds = max(0, int(seconds or 0))
    return f"{seconds // 60}:{str(seconds % 60).zfill(2)}"


def _payload():
    return request.get_json(silent=True) or request.form or {}


def _as_list(value):
    if value is None:
        return []

    if hasattr(value, "getlist"):
        return value.getlist("days")

    if isinstance(value, list):
        return value

    if isinstance(value, tuple):
        return list(value)

    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return []
        if "," in cleaned:
            return [item.strip() for item in cleaned.split(",") if item.strip()]
        return [cleaned]

    return [value]


def _as_int(value, default=0):
    try:
        return int(float(value))
    except Exception:
        return default


def _normalize_days(days):
    aliases = {
        "mon": "monday",
        "monday": "monday",
        "tue": "tuesday",
        "tues": "tuesday",
        "tuesday": "tuesday",
        "wed": "wednesday",
        "weds": "wednesday",
        "wednesday": "wednesday",
        "thu": "thursday",
        "thur": "thursday",
        "thurs": "thursday",
        "thursday": "thursday",
        "fri": "friday",
        "friday": "friday",
        "sat": "saturday",
        "saturday": "saturday",
        "sun": "sunday",
        "sunday": "sunday",
    }

    clean = []

    for day in _as_list(days):
        key = str(day or "").strip().lower()
        mapped = aliases.get(key, key)

        if mapped in DAY_LABELS:
            clean.append(mapped)

    ordered = []
    for day in clean:
        if day not in ordered:
            ordered.append(day)

    return ordered


def _normalize_zones(value):
    if value is None or value == "":
        return list(range(1, ZONE_COUNT + 1))

    if isinstance(value, list):
        raw = value
    elif isinstance(value, tuple):
        raw = list(value)
    elif isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"all", "all zones", "every", "every zone"}:
            return list(range(1, ZONE_COUNT + 1))
        raw = [item.strip() for item in lowered.replace(",", " ").split()]
    else:
        raw = [value]

    zones = []

    for item in raw:
        try:
            zone = int(float(item))
        except Exception:
            continue

        if 1 <= zone <= ZONE_COUNT and zone not in zones:
            zones.append(zone)

    return zones or list(range(1, ZONE_COUNT + 1))


def _program_from_payload(data):
    """
    Converts both native sprinkler payloads and Orion schedule payloads into the
    controller's expected program format.

    Native sprinkler format:
    {
        "start_time": "06:00",
        "days": ["monday", "tuesday"],
        "direction": "forward",
        "durations": [10, 10, 0, 0, 0, 0, 0, 0]
    }

    Orion format:
    {
        "start_time": "06:00",
        "days": ["mon", "tue"],
        "duration_minutes": 10,
        "zones": [1, 2, 3]
    }
    """

    if data is None:
        data = {}

    if hasattr(data, "to_dict"):
        data = data.to_dict(flat=False)

    if not isinstance(data, dict):
        data = {}

    # Accept nested program payload:
    # {"program": {...}}
    if isinstance(data.get("program"), dict):
        data = data.get("program") or {}

    start_time = (
        data.get("start_time")
        or data.get("time")
        or data.get("start")
        or ""
    )

    direction = str(data.get("direction") or "forward").strip().lower()
    if direction not in {"forward", "reverse"}:
        direction = "forward"

    days = _normalize_days(data.get("days"))

    durations = data.get("durations")

    # Native payload already has durations.
    if isinstance(durations, list):
        clean_durations = [_as_int(value, 0) for value in durations[:ZONE_COUNT]]

        while len(clean_durations) < ZONE_COUNT:
            clean_durations.append(0)

        clean_durations = [max(0, value) for value in clean_durations]
    else:
        # Orion-style payload: duration_minutes/minutes + zones.
        minutes = _as_int(
            data.get("duration_minutes", data.get("minutes", data.get("duration", 0))),
            0,
        )

        zones = _normalize_zones(data.get("zones"))
        clean_durations = [0] * ZONE_COUNT

        for zone in zones:
            index = int(zone) - 1
            if 0 <= index < ZONE_COUNT:
                clean_durations[index] = max(0, minutes)

    return {
        "start_time": str(start_time or "").strip(),
        "days": days,
        "direction": direction,
        "durations": clean_durations,
    }


def _status_with_schedule():
    status = get_public_state()
    program = load_program()
    schedule = compute_schedule(program)
    timeline = build_upcoming_timeline(program)

    status["program"] = program
    status["schedule"] = schedule
    status["computed_schedule"] = schedule

    status["timeline"] = timeline
    status["upcoming_timeline"] = timeline
    status["upcoming_zone_timeline"] = timeline
    status["upcoming_zones"] = timeline

    status["next_run"] = next_run(program)

    return status


def _program_response(program):
    schedule = compute_schedule(program)
    timeline = build_upcoming_timeline(program)

    return {
        "ok": True,
        "program": program,
        "schedule": schedule,
        "computed_schedule": schedule,
        "timeline": timeline,
        "upcoming_timeline": timeline,
        "upcoming_zone_timeline": timeline,
        "upcoming_zones": timeline,
        "next_run": next_run(program),
    }


def register_routes(app):
    @app.route("/")
    def index():
        program = load_program()
        status = get_public_state()
        schedule = compute_schedule(program)
        timeline = build_upcoming_timeline(program)

        return render_template(
            "index.html",
            current_program=program,
            cycle_status=status,
            zones=status.get("zones", [False] * ZONE_COUNT),
            day_labels=DAY_LABELS,
            schedules=schedule,
            upcoming_timeline=timeline,
            next_run=next_run(program),
            format_remaining=format_remaining,
        )

    @app.route("/api/status")
    @app.route("/api/sprinkler/status")
    @app.route("/api/sprinkler/health")
    @app.route("/status")
    def api_status():
        return jsonify(_status_with_schedule())

    @app.route("/save_program", methods=["POST"])
    def save_program_route():
        data = _payload()

        days = data.getlist("days") if hasattr(data, "getlist") else data.get("days", [])
        if isinstance(days, str):
            days = [days]

        durations = []

        for index in range(ZONE_COUNT):
            raw = data.get(f"zone{index}", 0)

            try:
                durations.append(max(0, int(float(raw or 0))))
            except Exception:
                durations.append(0)

        program = {
            "start_time": str(data.get("start_time", "")).strip(),
            "days": days,
            "direction": str(data.get("direction", "forward")).strip().lower(),
            "durations": durations,
        }

        save_program(program)

        return redirect(url_for("index"))

    @app.route("/delete_program", methods=["POST"])
    def delete_program_route():
        delete_program()

        return redirect(url_for("index"))

    @app.route("/run_cycle", methods=["POST"])
    def run_cycle_route():
        start_program_async()

        return redirect(url_for("index"))

    @app.route("/on/<int:zone>", methods=["POST"])
    def zone_on_route(zone):
        data = _payload()
        duration = int(float(data.get("duration", data.get("minutes", 1)) or 1))

        if zone < 0 or zone >= ZONE_COUNT:
            return jsonify({"ok": False, "error": "zone out of range"}), 400

        start_manual_zone_async(zone, duration)

        return redirect(url_for("index"))

    @app.route("/off/<int:zone>", methods=["POST"])
    def zone_off_route(zone):
        emergency_stop(f"force off zone {zone + 1}")

        return redirect(url_for("index"))

    @app.route("/off", methods=["POST"])
    @app.route("/stop", methods=["POST"])
    @app.route("/api/stop", methods=["POST"])
    @app.route("/api/sprinkler/stop", methods=["POST"])
    def stop_route():
        emergency_stop("api stop")

        return jsonify({"ok": True, "action": "stop"})

    @app.route("/api/sprinkler/zone", methods=["POST"])
    @app.route("/api/zone", methods=["POST"])
    def api_zone():
        data = _payload()

        zone = int(float(data.get("zone", 0)))
        duration = int(float(data.get("duration", data.get("minutes", 1))))

        if zone < 1 or zone > ZONE_COUNT:
            return jsonify({"ok": False, "error": "zone out of range"}), 400

        start_manual_zone_async(zone - 1, duration)

        return jsonify({"ok": True, "zone": zone, "duration": duration})

    @app.route("/api/program", methods=["GET", "POST", "PUT", "DELETE"])
    @app.route("/api/sprinkler/program", methods=["GET", "POST", "PUT", "DELETE"])
    def api_program():
        if request.method == "GET":
            program = load_program()
            return jsonify(_program_response(program))

        if request.method == "DELETE":
            delete_program()
            program = load_program()
            return jsonify(_program_response(program))

        data = _payload()
        program_payload = _program_from_payload(data)
        program = save_program(program_payload)

        return jsonify(_program_response(program))
