from .solarassistant import SolarAssistantInverter
from .solarman import SolarmanInverter

# from .deye_synsynk import SynsynkInverter
# from .growatt import GrowattInverter

INVERTER_INTEGRATIONS = {
    # "Synsynk": SynsynkInverter,
    "SolarAssistant": SolarAssistantInverter,
    "Solarman": SolarmanInverter,
    "Sunsynk": SunsynkInverter,
}


def get_inverter_class(model_name):
    try:
        return INVERTER_INTEGRATIONS[model_name]
    except KeyError:
        raise ValueError(f"Unsupported inverter model: {model_name}")
