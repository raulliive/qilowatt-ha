import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from qilowatt import EnergyData, MetricsData

from .base_inverter import BaseInverter

_LOGGER = logging.getLogger(__name__)


class SunsynkInverter(BaseInverter):
    """Implementation for Sunsynk integration for Deye Investers. https://github.com/kellerza/sunsynk"""

    def __init__(self, hass: HomeAssistant, config_entry):
        super().__init__(hass, config_entry)
        self.hass = hass
        self.device_id = config_entry.data["device_id"]
        self.entity_registry = er.async_get(hass)
        self.inverter_entities = {}
        for entity in self.entity_registry.entities.values():
            if entity.device_id == self.device_id:
                self.inverter_entities[entity.entity_id] = entity.name

    def find_entity_state(self, entity_id):
        """Helper method to find a state by entity_id."""
        return next(
            (
                self.hass.states.get(entity)
                for entity in self.inverter_entities
                if entity.endswith(entity_id)
            ),
            None,
        )

    def get_state_float(self, entity_id, default=0.0):
        """Helper method to get a sensor state as float."""

        state = self.find_entity_state(entity_id)
        if state and state.state not in ("unknown", "unavailable", ""):
            try:
                return float(state.state)
            except ValueError:
                _LOGGER.warning(f"Could not convert state of {entity_id} to float")
        else:
            _LOGGER.warning(f"State of {entity_id} is unavailable or unknown")
        return default

    def get_state_int(self, entity_id, default=0):
        """Helper method to get a sensor state as int."""
        state = self.find_entity_state(entity_id)
        if state and state.state not in ("unknown", "unavailable", ""):
            try:
                return int(float(state.state))
            except ValueError:
                _LOGGER.warning(f"Could not convert state of {entity_id} to int")
        else:
            _LOGGER.warning(f"State of {entity_id} is unavailable or unknown")
        return default

    def get_energy_data(self):
        """Retrieve ENERGY data."""
        power = [
            self.get_state_float("ss_grid_l1_power"),
            self.get_state_float("ss_grid_l2_power"),
            self.get_state_float("ss_grid_l3_power"),
        ]
        today = self.get_state_float("ss_day_grid_import")
        total = 0.0  # As per payload
        voltage = [
            self.get_state_float("ss_grid_l1_voltage"),
            self.get_state_float("ss_grid_l2_voltage"),
            self.get_state_float("ss_grid_l3_voltage"),
        ]
        current = [round(x / y, 2) for x, y in zip(power, voltage)]
        frequency = self.get_state_float("ss_grid_frequency")

        return EnergyData(
            Power=power,
            Today=today,
            Total=total,
            Current=current,
            Voltage=voltage,
            Frequency=frequency,
        )

    def get_metrics_data(self):
        """Retrieve METRICS data."""
        pv_power = [
            self.get_state_float("ss_pv1_power"),
            self.get_state_float("ss_pv2_power"),
        ]
        pv_voltage = [
            self.get_state_float("ss_pv1_voltage"),
            self.get_state_float("ss_pv1_voltage"),
        ]
        pv_current = [
            self.get_state_float("ss_pv1_current"),
            self.get_state_float("ss_pv2_current"),
        ]
        load_power = [
            self.get_state_float("ss_load_l1_power"),
            self.get_state_float("ss_load_l2_power"),
            self.get_state_float("ss_load_l3_power"),
        ]
        alarm_codes = [0, 0, 0, 0, 0, 0]  # As per payload
        battery_soc = self.get_state_int("ss_battery_soc")
        load_current = [0.0, 0.0, 0.0]  # As per payload
        battery_power = [-1 * self.get_state_float("ss_battery_power")]
        battery_current = [-1 * self.get_state_float("ss_battery_current")]
        battery_voltage = [self.get_state_float("ss_battery_voltage")]
        inverter_status = 2  # As per payload
        grid_export_limit = self.get_state_float("number.ss_export_limit_power")
        battery_temperature = [self.get_state_float("ss_battery_temperature")]
        inverter_temperature = self.get_state_float("ss_radiator_temperature")

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
