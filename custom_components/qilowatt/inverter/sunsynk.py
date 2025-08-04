import logging
import time
from typing import Iterable

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from qilowatt import EnergyData, MetricsData

from .base_inverter import BaseInverter
from ..const import CONF_SUNSYNK_PREFIX

_LOGGER = logging.getLogger(__name__)

# Domains from which we accept sensor data (full entity‑id starts with one of these)
_ALLOWED_DOMAINS: tuple[str, ...] = ("sensor.", "number.")

# How often (seconds) we rebuild the entity list for the selected device
_CACHE_TTL = 30


class SunsynkInverter(BaseInverter):
    """Read data from Sunsynk‑MQTT style sensors for Qilowatt."""

    def __init__(self, hass: HomeAssistant, config_entry):
        super().__init__(hass, config_entry)
        self.hass = hass
        self.device_id = config_entry.data["device_id"]
        self.prefix: str = (config_entry.data.get(CONF_SUNSYNK_PREFIX) or "ss").strip() or "ss"

        # Registry is cheap; we refresh the entity list lazily (see _refresh_entity_cache)
        self.entity_registry = er.async_get(hass)
        self.inverter_entities: set[str] = set()
        self._cache_ts: float = 0.0
        self._refresh_entity_cache(force=True)

    # ------------------------------------------------------------------
    # cache helpers
    # ------------------------------------------------------------------
    def _refresh_entity_cache(self, *, force: bool = False) -> None:
        """(Re)build the set of entity_ids belonging to *self.device_id*.

        To avoid scanning the whole registry on every sensor read we refresh
        at most once every `_CACHE_TTL` seconds unless *force* is True."""
        if not force and time.time() - self._cache_ts < _CACHE_TTL:
            return
        self.inverter_entities = {
            e.entity_id
            for e in self.entity_registry.entities.values()
            if e.device_id == self.device_id
        }
        self._cache_ts = time.time()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _eid(self, suffix: str, domain: str | None = None) -> str:
        """Return either `prefix_suffix` or `domain.prefix_suffix`."""
        body = f"{self.prefix}{suffix}" if self.prefix.endswith("_") else f"{self.prefix}_{suffix}"
        return f"{domain}.{body}" if domain else body

    def _lookup_state(self, eid_suffix_or_full: str) -> State | None:
        """Find a HA State by full id or suffix.

        If `eid_suffix_or_full` contains a dot we treat it as a *full* entity
        id and do a direct lookup; otherwise we match suffices within the
        cached entity set. Only entities whose domain is in _ALLOWED_DOMAINS
        are considered."""
        self._refresh_entity_cache()

        # full entity-id path (has a domain prefix)
        if "." in eid_suffix_or_full:
            st = self.hass.states.get(eid_suffix_or_full)
            if st and st.entity_id.startswith(_ALLOWED_DOMAINS):
                return st
            return None

        # suffix search
        for eid in self.inverter_entities:
            if not eid.startswith(_ALLOWED_DOMAINS):
                continue
            if eid.endswith(eid_suffix_or_full):
                return self.hass.states.get(eid)
        return None

    def _as_number(self, state: State | None, default: float = 0.0) -> float:
        if state and state.state not in ("unknown", "unavailable", ""):
            try:
                return float(state.state.split()[0])  # strip unit if present
            except ValueError:
                _LOGGER.debug("Could not parse %s as number", state.entity_id)
        return default

    # convenience wrappers ------------------------------------------------
    def get_state_float(self, ent_id: str, default: float = 0.0) -> float:
        return self._as_number(self._lookup_state(ent_id), default)

    def get_state_int(self, ent_id: str, default: int = 0) -> int:
        return int(round(self.get_state_float(ent_id, float(default))))

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
        if any(v == 0 for v in voltage):
            _LOGGER.debug("Voltage is 0 on at least one phase; current set to 0")
        frequency = self.get_state_float(self._eid("grid_frequency"))

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
        battery_soc = self.get_state_int(self._eid("battery_soc"))

        # sign convention optional—assume Sunsynk publishes battery discharge as POSITIVE → convert to negative (export)
        raw_batt_power = self.get_state_float(self._eid("battery_power"))
        battery_power = [-abs(raw_batt_power)]
        battery_current = [-abs(self.get_state_float(self._eid("battery_current")))]

        battery_voltage = [self.get_state_float(self._eid("battery_voltage"))]
        grid_export_limit = self.get_state_float(self._eid("export_limit_power", domain="number"))
        battery_temperature = [self.get_state_float(self._eid("battery_temperature"))]
        inverter_temperature = self.get_state_float(self._eid("radiator_temperature"))

        return MetricsData(
            PvPower=pv_power,
            PvVoltage=pv_voltage,
            PvCurrent=pv_current,
            LoadPower=load_power,
            AlarmCodes=[0] * 6,
            BatterySOC=battery_soc,
            LoadCurrent=[0.0, 0.0, 0.0],
            BatteryPower=battery_power,
            BatteryCurrent=battery_current,
            BatteryVoltage=battery_voltage,
            InverterStatus=2,
            GridExportLimit=grid_export_limit,
            BatteryTemperature=battery_temperature,
            InverterTemperature=inverter_temperature,
        )

