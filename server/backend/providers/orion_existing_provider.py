from typing import Dict, Any
import os
import requests

from providers.thermostat_provider import ThermostatProvider


HVAC_URL = os.getenv(
    "ORION_EXISTING_HVAC_URL",
    "http://thermostat-controller.local:5002/api/hvac/status",
)


class OrionExistingProvider(ThermostatProvider):
    provider_name = "orion_existing_hvac"

    def get_state(self) -> Dict[str, Any]:
        try:
            response = requests.get(HVAC_URL, timeout=5)
            response.raise_for_status()

            data = response.json()

            temperature = (
                data.get("temperature")
                or data.get("temp")
                or data.get("current_temp")
            )

            setpoint = (
                data.get("setpoint")
                or data.get("target_setpoint")
                or data.get("target_temperature")
            )

            cooling = bool(data.get("cooling") or data.get("cooling_active"))
            heating = bool(data.get("heating") or data.get("heating_active"))
            fan = bool(data.get("fan") or data.get("fan_on") or data.get("fan_active"))

            if cooling:
                equipment_state = "cooling"
            elif heating:
                equipment_state = "heating"
            elif fan:
                equipment_state = "fan"
            else:
                equipment_state = "idle"

            return {
                "id": "t6pro_living_room",
                "name": "RPi4 / ESP32 HVAC Thermostat",
                "vendor": "Orion Field Controller",
                "model": "Raspberry Pi 4 + ESP32 Relay Node",
                "provider": self.provider_name,
                "online": data.get("online", data.get("node_online", True)),
                "temperature": temperature,
                "humidity": data.get("humidity"),
                "setpoint": setpoint,
                "mode": data.get("mode") or data.get("hvac_mode") or data.get("system_mode"),
                "fan_mode": data.get("fan_mode"),
                "equipment_state": equipment_state,
                "cooling": cooling,
                "heating": heating,
                "fan": fan,
                "raw": data,
            }

        except Exception as exc:
            return {
                "id": "t6pro_living_room",
                "name": "RPi4 / ESP32 HVAC Thermostat",
                "vendor": "Orion Field Controller",
                "model": "Raspberry Pi 4 + ESP32 Relay Node",
                "provider": self.provider_name,
                "online": False,
                "fault": str(exc),
                "raw": {
                    "url": HVAC_URL,
                    "error": str(exc),
                },
            }

    def set_setpoint(self, temperature: float) -> Dict[str, Any]:
        return {
            "ok": False,
            "message": "Not implemented yet"
        }

    def set_mode(self, mode: str) -> Dict[str, Any]:
        return {
            "ok": False,
            "message": "Not implemented yet"
        }
