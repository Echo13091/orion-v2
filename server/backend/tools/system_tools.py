from core.state import get_state_snapshot


def get_system_status():
    return get_state_snapshot()


def get_observation_summary():
    snapshot = get_state_snapshot()
    return {
        "cpu": snapshot["cpu"],
        "memory": snapshot["memory"],
        "mode": snapshot["mode"],
        "fault": snapshot["fault"],
    }