from tools.environment import evaluate_environment


def weather(rain_chance=0, online=True):
    return {
        "online": online,
        "rain_chance": rain_chance,
        "temp": 85,
        "feels_like": 93,
        "humidity": 73,
    }


def test_physical_rain_sensor_is_not_treated_as_vision():
    result = evaluate_environment(
        grass_condition=None,
        weather=weather(rain_chance=100),
        sprinkler={
            "online": True,
            "rain_sensor": {
                "wet": False,
                "status": "dry",
                "blocks_schedule": True,
            },
        },
        rain_detection={
            "wet": False,
            "status": "dry",
        },
    )

    evidence = result["evidence"]

    assert "weather" in evidence["trusted_inputs"]
    assert "irrigation_controller" in evidence["trusted_inputs"]
    assert "physical_rain_sensor" in evidence["trusted_inputs"]
    assert "vision_snapshot" not in evidence["trusted_inputs"]

    assert evidence["physical_rain_sensor"]["trusted"] is True
    assert evidence["physical_rain_sensor"]["wet"] is False
    assert evidence["vision"]["trusted"] is False

    ignored = {item["input"] for item in evidence["ignored_inputs"]}
    assert "vision_snapshot" in ignored
    assert "lawn_analysis" in ignored


def test_missing_rain_sensor_is_not_marked_trusted():
    result = evaluate_environment(
        grass_condition=None,
        weather=weather(rain_chance=0),
        sprinkler={"online": True},
        rain_detection={},
    )

    evidence = result["evidence"]

    assert "physical_rain_sensor" not in evidence["trusted_inputs"]
    assert evidence["physical_rain_sensor"]["trusted"] is False


def test_controller_offline_creates_safety_blocker():
    result = evaluate_environment(
        grass_condition=None,
        weather=weather(rain_chance=0),
        sprinkler={"online": False},
        rain_detection={},
    )

    evidence = result["evidence"]

    assert evidence["quality"] == "blocked"
    assert evidence["blockers"]
    assert evidence["blockers"][0]["blocker"] == "irrigation_controller_offline"
    assert result["safety"]["blocked_by"] == evidence["blockers"]
    assert result["recommendation"] == "monitor_lawn"


def test_physical_rain_sensor_wet_overrides_lawn_appearance():
    result = evaluate_environment(
        grass_condition={
            "ok": True,
            "condition": "poor",
            "score": 10,
            "dryness_index": 0.95,
            "valid_percent": 80,
        },
        weather=weather(rain_chance=0),
        sprinkler={
            "online": True,
            "rain_sensor": {
                "wet": True,
                "status": "wet",
                "blocks_schedule": True,
            },
        },
        rain_detection={},
    )

    assert result["recommendation"] == "delay_irrigation"
    assert result["confidence"] == "high"
    assert result["evidence"]["physical_rain_sensor"]["wet"] is True


def test_camera_metrics_are_required_for_trusted_vision():
    result = evaluate_environment(
        grass_condition=None,
        weather=weather(rain_chance=0),
        sprinkler={"online": True},
        rain_detection={
            "ok": True,
            "rain_detected": False,
            "wetness_score": 0.48,
            "motion_score": 0.0,
            "confidence": "medium",
        },
    )

    evidence = result["evidence"]

    assert evidence["vision"]["trusted"] is True
    assert "vision_snapshot" in evidence["trusted_inputs"]
