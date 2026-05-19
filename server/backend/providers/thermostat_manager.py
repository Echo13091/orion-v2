from providers.orion_existing_provider import OrionExistingProvider
from providers.resideo_provider import ResideoProvider


THERMOSTAT_PROVIDERS = {
    "orion_existing_hvac": OrionExistingProvider(),
    "resideo_t6": ResideoProvider(),
}


ACTIVE_PROVIDER = "orion_existing_hvac"


def get_provider():
    return THERMOSTAT_PROVIDERS[ACTIVE_PROVIDER]


def get_thermostat_state():
    provider = get_provider()
    return provider.get_state()
