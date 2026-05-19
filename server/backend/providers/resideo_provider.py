from typing import Dict, Any

from providers.thermostat_provider import ThermostatProvider


class ResideoProvider(ThermostatProvider):
    provider_name = "resideo_t6"

    def get_state(self) -> Dict[str, Any]:
        return {
            "provider": self.provider_name,
            "online": False,
            "message": "Waiting for Resideo API approval"
        }

    def set_setpoint(self, temperature: float) -> Dict[str, Any]:
        return {
            "ok": False,
            "message": "Resideo integration not enabled"
        }

    def set_mode(self, mode: str) -> Dict[str, Any]:
        return {
            "ok": False,
            "message": "Resideo integration not enabled"
        }
