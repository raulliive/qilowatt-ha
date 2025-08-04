import logging
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from qilowatt import EnergyData, MetricsData

from .base_inverter import BaseInverter
from ..const import CONF_SUNSYNK_PREFIX

_LOGGER = logging.getLogger(__name__)

class SunsynkInverter(BaseInverter):
    """Implementation for Sunsynk integration for Deye Inverters."""

    def __init__(self, hass: HomeAssistant, config_entry):
        super().__init__(hass, config_entry)
        self.hass = hass
        self.device_id = config_entry.data["device_id"]
        self.prefix = (config_entry.data.get(CONF_SUNSYNK_PREFIX) or "ss").strip()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _eid(self, suffix: str, domain: str | None = None) -> str:
        """Build entity-ID suffix using the configured prefix."""
        body = (
            f"{self.prefix}{suffix}" if self.prefix.endswith("_") else f"{self.prefix}_{suffix}"
        )
        return f"{domain}.{body}" if domain else body

    def _get_state(self, entity_id_suffix: str, domain: str | None = None) -> State | None:
        """Get the state object for a given entity_id suffix."""
        entity_id = self._eid(entity_id_suffix, domain)
        return self.hass.states.get(entity_id)

    def get_state_float(self, entity_id_suffix: str, domain: str | None = None, default: float = 0.0) -> float:
        """Return the state as a float for a given entity_id suffix."""
        state = self._get_state(entity_id_suffix, domain)
        if state and state.state not in ("unknown", "unavailable", ""):
            try:
                return float(state.state)
            except (ValueError, TypeError):
                _LOGGER.debug("Could not convert state '%s' for entity '%s' to float", state.state, state.entity_id)
        return default

    def get_state_int(self, entity_id_suffix: str, domain: str | None = None, default: int = 0) -> int:
        """Return the state as an int for a given entity_id suffix."""
        state = self._get_state(entity_id_suffix, domain)
        if state and state.state not in ("unknown", "unavailable", ""):
            try:
                return int(float(state.state))
            except (ValueError, TypeError):
                _LOGGER.debug("Could not convert state '%s' for entity '%s' to int", state.state, state.entity_id)
        return default

    # ------------------------------------------------------------------
    # data builders
    # ------------------------------------------------------------------
    def get_energy_data(self) -> EnergyData:
        power = [
            self.get_state_float("grid_l1_power"),
            self.get_state_float("grid_l2_power"),
            self.get_state_float("grid_l3_power"),
        ]
        today = self.get_state_float("day_grid_import")
        voltage = [
            self.get_state_float("grid_l1_voltage"),
            self.get_state_float("grid_l2_voltage"),
            self.get_state_float("grid_l3_voltage"),
        ]
        current = [round(p / v, 2) if v else 0.0 for p, v in zip(power, voltage)]
        frequency = self.get_state_float("grid_frequency")

        return EnergyData(
            Power=power,
            Today=today,
            Total=0.0,
            Current=current,
            Voltage=voltage,
            Frequency=frequency,
        )

    def get_metrics_data(self) -> MetricsData:
        pv_power = [
            self.get_state_float("pv1_power"),
            self.get_state_float("pv2_power"),
        ]
        pv_voltage = [
            self.get_state_float("pv1_voltage"),
            self.get_state_float("pv2_voltage"),
        ]
        pv_current = [
            self.get_state_float("pv1_current"),
            self.get_state_float("pv2_current"),
        ]
        load_power = [
            self.get_state_float("load_l1_power"),
            self.get_state_float("load_l2_power"),
            self.get_state_float("load_l3_power"),
        ]
        alarm_codes = [0, 0, 0, 0, 0, 0]
        battery_soc = self.get_state_int("battery_soc")
        load_current = [0.0, 0.0, 0.0]
        battery_power = [-1 * self.get_state_float("battery_power")]
        battery_current = [-1 * self.get_state_float("battery_current")]
        battery_voltage = [self.get_state_float("battery_voltage")]
        inverter_status = 2
        grid_export_limit = self.get_state_float("export_limit_power", domain="number")
        battery_temperature = [self.get_state_float("battery_temperature")]
        inverter_temperature = self.get_state_float("radiator_temperature")

        return MetricsData(
            PvPower=pv_power,
            PvVoltage=pv_voltage,
            PvCurrent=pv_current,
            LoadPower=load_power,
            AlarmCodes=alarm_codes,
            BatterySOC=battery_soc,
            LoadCurrent=load_current,
            BatteryPower=battery_power,
            BatteryCurrent=battery_current,
            BatteryVoltage=battery_voltage,
            InverterStatus=inverter_status,
            GridExportLimit=grid_export_limit,
            BatteryTemperature=battery_temperature,
            InverterTemperature=inverter_temperature,
        )
