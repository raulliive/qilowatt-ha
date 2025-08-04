import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from qilowatt import EnergyData, MetricsData

from .base_inverter import BaseInverter
from ..const import CONF_SUNSYNK_PREFIX

_LOGGER = logging.getLogger(__name__)


class SunsynkInverter(BaseInverter):
    """Implementation for Sunsynk integration for Deye Inverters. https://github.com/kellerza/sunsynk"""

    def __init__(self, hass: HomeAssistant, config_entry):
        super().__init__(hass, config_entry)
        self.hass = hass
        self.device_id = config_entry.data["device_id"]
        self.prefix = (config_entry.data.get(CONF_SUNSYNK_PREFIX) or "ss").strip()

        # Registry is cheap to keep; the entity list is rebuilt on demand
        self.entity_registry = er.async_get(hass)
        self.inverter_entities: dict[str, str] = {}
        self._refresh_entity_cache()

    # ------------------------------------------------------------------
    # cache helpers
    # ------------------------------------------------------------------
    def _refresh_entity_cache(self) -> None:
        """Refresh local cache so late-created entities are found."""
        self.inverter_entities = {
            e.entity_id: e.name
            for e in self.entity_registry.entities.values()
            if e.device_id == self.device_id
        }

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _eid(self, suffix: str, domain: str | None = None) -> str:
        """Build entity-ID suffix using the configured prefix."""
        body = (
            f"{self.prefix}{suffix}" if self.prefix.endswith("_") else f"{self.prefix}_{suffix}"
        )
        return f"{domain}.{body}" if domain else body

    def find_entity_state(self, entity_id: str):
        """Return Home Assistant state whose entity_id ends with *entity_id*."""
        self._refresh_entity_cache()  # keep cache fresh
        return next(
            (self.hass.states.get(eid) for eid in self.inverter_entities if eid.endswith(entity_id)),
            None,
        )

    def get_state_float(self, entity_id: str, default: float = 0.0) -> float:
        state = self.find_entity_state(entity_id)
        if state and state.state not in ("unknown", "unavailable", ""):
            try:
                return float(state.state)
            except ValueError:
                _LOGGER.debug("Could not convert %s to float", entity_id)
        return default

    def get_state_int(self, entity_id: str, default: int = 0) -> int:
        state = self.find_entity_state(entity_id)
        if state and state.state not in ("unknown", "unavailable", ""):
            try:
                return int(float(state.state))
            except ValueError:
                _LOGGER.debug("Could not convert %s to int", entity_id)
        return default

    # ------------------------------------------------------------------
    # data builders
    # ------------------------------------------------------------------
    def get_energy_data(self) -> EnergyData:
        power = [
            self.get_state_float(self._eid("grid_l1_power")),
            self.get_state_float(self._eid("grid_l2_power")),
            self.get_state_float(self._eid("grid_l3_power")),
        ]
        today = self.get_state_float(self._eid("day_grid_import"))
        voltage = [
            self.get_state_float(self._eid("grid_l1_voltage")),
            self.get_state_float(self._eid("grid_l2_voltage")),
            self.get_state_float(self._eid("grid_l3_voltage")),
        ]
        current = [round(p / v, 2) if v else 0.0 for p, v in zip(power, voltage)]
        frequency = self.get_state_float(self._eid("grid_frequency"))

        return EnergyData(
            Power=power,
            Today=today,
            Total=0.0,  # not provided
            Current=current,
            Voltage=voltage,
            Frequency=frequency,
        )

    def get_metrics_data(self) -> MetricsData:
        pv_power = [
            self.get_state_float(self._eid("pv1_power")),
            self.get_state_float(self._eid("pv2_power")),
        ]
        pv_voltage = [
            self.get_state_float(self._eid("pv1_voltage")),
            self.get_state_float(self._eid("pv2_voltage")),
        ]
        pv_current = [
            self.get_state_float(self._eid("pv1_current")),
            self.get_state_float(self._eid("pv2_current")),
        ]
        load_power = [
            self.get_state_float(self._eid("load_l1_power")),
            self.get_state_float(self._eid("load_l2_power")),
            self.get_state_float(self._eid("load_l3_power")),
        ]
        alarm_codes = [0, 0, 0, 0, 0, 0]  # As per payload
        battery_soc = self.get_state_int(self._eid("battery_soc"))
        load_current = [0.0, 0.0, 0.0]  # As per payload
        battery_power = [-1 * self.get_state_float(self._eid("battery_power"))]
        battery_current = [-1 * self.get_state_float(self._eid("battery_current"))]
        battery_voltage = [self.get_state_float(self._eid("battery_voltage"))]
        inverter_status = 2  # As per payload
        grid_export_limit = self.get_state_float(self._eid("export_limit_power", domain="number"))
        battery_temperature = [self.get_state_float(self._eid("battery_temperature"))]
        inverter_temperature = self.get_state_float(self._eid("radiator_temperature"))

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
