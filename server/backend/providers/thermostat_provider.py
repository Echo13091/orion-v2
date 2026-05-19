from typing import Dict, Any


class ThermostatProvider:
    provider_name = "base"

    def get_state(self) -> Dict[str, Any]:
        raise NotImplementedError()

    def set_setpoint(self, temperature: float) -> Dict[str, Any]:
        raise NotImplementedError()

    def set_mode(self, mode: str) -> Dict[str, Any]:
        raise NotImplementedError()
