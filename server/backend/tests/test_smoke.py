import os

os.environ["ORION_DISABLE_STARTUP"] = "1"
os.environ["ORION_EDGE_MODE"] = "1"
os.environ["ORION_LLM_ENABLED"] = "0"
os.environ["ORION_CODE_LLM_ENABLED"] = "0"
os.environ["ORION_EVENT_LOG_PATH"] = "/tmp/orion_test_events.jsonl"

from app import app


def test_health_route():
    client = app.test_client()
    response = client.get("/v1/health")

    assert response.status_code == 200
    payload = response.get_json()

    assert payload["ok"] is True
    assert payload["service"] == "orion-backend"


def test_readiness_route():
    client = app.test_client()
    response = client.get("/v1/readiness")

    assert response.status_code == 200
    payload = response.get_json()

    assert payload["ok"] is True
    assert payload["ready"] is True


def test_version_route():
    client = app.test_client()
    response = client.get("/v1/version")

    assert response.status_code == 200
    payload = response.get_json()

    assert payload["ok"] is True
    assert payload["service"] == "orion-backend"


def test_events_route():
    client = app.test_client()
    response = client.get("/v1/events?limit=10&compact=true")

    assert response.status_code == 200
    payload = response.get_json()

    assert payload["ok"] is True
    assert "events" in payload
    assert isinstance(payload["events"], list)


def test_faults_route():
    client = app.test_client()
    response = client.get("/v1/faults")

    assert response.status_code == 200
    payload = response.get_json()

    assert payload["ok"] is True
    assert "faults" in payload
    assert isinstance(payload["faults"], list)


def test_system_decision_route():
    client = app.test_client()
    response = client.get("/v1/system/decision")

    assert response.status_code == 200
    payload = response.get_json()

    assert payload["ok"] is True
    assert "sprinkler" in payload
    assert "thermostat" in payload
    assert "environment" in payload
