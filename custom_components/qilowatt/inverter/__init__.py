from .huawei import HuaweiInverter
from .solarassistant import SolarAssistantInverter
from .solarman import SolarmanInverter
from .solarman_sofar import SolarmanSofarInverter
from .sofar import SofarInverter
from .esphome import EspHomeInverter
from .victron import VictronInverter
from .sunsynk import SunsynkInverter

# from .deye_synsynk import SynsynkInverter
# from .growatt import GrowattInverter

INVERTER_INTEGRATIONS = {
    "SolarAssistant": SolarAssistantInverter,
    "Solarman": SolarmanInverter,
    "SolarmanSofar": SolarmanSofarInverter,
    "Sofar": SofarInverter,
    "Huawei": HuaweiInverter,
    "EspHome": EspHomeInverter,
    "Victron": VictronInverter,
    "Sunsynk": SunsynkInverter,
}


def get_inverter_class(model_name):
    try:
        return INVERTER_INTEGRATIONS[model_name]
    except KeyError:
        raise ValueError(f"Unsupported inverter model: {model_name}")
