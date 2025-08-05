import logging
from typing import Iterable

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from qilowatt import EnergyData, MetricsData

from .base_inverter import BaseInverter
from ..const import CONF_SUNSYNK_PREFIX

_LOGGER = logging.getLogger(__name__)

# Domains we accept values from
_ALLOWED_DOMAINS: tuple[str, ...] = ("sensor.", "number.")


class SunsynkInverter(BaseInverter):
    """Read Sunsynk‑MQTT style sensors and expose them to Qilowatt.

    Caching has been **removed** – every lookup pulls the latest entity list so
    newly‑created sensors are available immediately. Enable verbose logs with:

    ```yaml
    logger:
      logs:
        custom_components.qilowatt.inverter.sunsynk: debug
    ```
    """

    # ------------------------------------------------------------------
    # life‑cycle
    # ------------------------------------------------------------------
    def __init__(self, hass: HomeAssistant, config_entry):
        super().__init__(hass, config_entry)
        self.hass = hass
        self.device_id = config_entry.data["device_id"]
        self.prefix: str = (config_entry.data.get(CONF_SUNSYNK_PREFIX) or "ss").strip() or "ss"

        self.entity_registry = er.async_get(hass)

        _LOGGER.debug(
            "SunsynkInverter initialised (device_id=%s, prefix='%s')",
            self.device_id,
            self.prefix,
        )

    # ------------------------------------------------------------------
    # lookup helpers
    # ------------------------------------------------------------------
    def _eid(self, suffix: str, domain: str | None = None) -> str:
        """Return a full entity‑id string.

        * If *domain* is ``None`` we assume the normal sensor domain and prepend
          ``sensor.`` automatically, so callers only specify the *suffix*.
        * If *domain* is given (e.g. "number") we honour it.
        """
        body = f"{self.prefix}{suffix}" if self.prefix.endswith("_") else f"{self.prefix}_{suffix}"
        domain = domain or "sensor"
        full = f"{domain}.{body}"
        _LOGGER.debug("_eid: suffix='%s', domain=%s → '%s'", suffix, domain, full)
        return full

    def _lookup_state(self, suffix_or_full: str) -> State | None:
        """Return latest state for *suffix_or_full* (no caching)."""
        # Full ID – direct lookup
        if "." in suffix_or_full:
            st = self.hass.states.get(suffix_or_full)
            _LOGGER.debug("Lookup(full): %s → %s", suffix_or_full, st.state if st else "None")
            return st if st and st.entity_id.startswith(_ALLOWED_DOMAINS) else None

        # Suffix search – enumerate device's entities every time
        for ent in self.entity_registry.entities.values():
            if ent.device_id != self.device_id:
                continue
            if not ent.entity_id.startswith(_ALLOWED_DOMAINS):
                continue
            if ent.entity_id.endswith(suffix_or_full):
                st = self.hass.states.get(ent.entity_id)
                _LOGGER.debug("Lookup(suffix): '%s' matched '%s' → %s", suffix_or_full, ent.entity_id, st.state)
                return st
        _LOGGER.debug("Lookup(suffix): '%s' not found", suffix_or_full)
        return None

    def _as_number(self, state: State | None, default: float = 0.0) -> float:
        if state and state.state not in ("unknown", "unavailable", ""):
            try:
                value = float(state.state.split()[0])
                _LOGGER.debug("Parsed number %s from %s", value, state.entity_id)
                return value
            except ValueError:
                _LOGGER.debug("Failed to parse number from %s ('%s')", state.entity_id, state.state)
        return default

    # convenience wrappers ------------------------------------------------
    def get_state_float(self, ent: str, default: float = 0.0, domain: str | None = None) -> float:
        value = self._as_number(self._lookup_state(self._eid(ent, domain)), default)
        _LOGGER.debug("get_state_float('%s') → %s", ent, value)
        return value

    def get_state_int(self, ent: str, default: int = 0, domain: str | None = None) -> int:
        value = int(round(self.get_state_float(ent, float(default), domain)))
        _LOGGER.debug("get_state_int('%s') → %s", ent, value)
        return value

    # ------------------------------------------------------------------
    # data builders (unchanged)
    # ------------------------------------------------------------------
    def get_energy_data(self) -> EnergyData:
        _LOGGER.debug("Building EnergyData …")
        power = [
            self.get_state_float("grid_l1_power"),
            self.get_state_float("grid_l2_power"),
            self.get_state_float("grid_l3_power"),
        ]
        voltage = [
            self.get_state_float("grid_l1_voltage"),
            self.get_state_float("grid_l2_voltage"),
            self.get_state_float("grid_l3_voltage"),
        ]
        current = [round(p / v, 2) if v else 0.0 for p, v in zip(power, voltage)]
        if any(v == 0 for v in voltage):
            _LOGGER.debug("Voltage is 0 on at least one phase; current set to 0")
        today = self.get_state_float("day_grid_import")
        frequency = self.get_state_float("grid_frequency")

        data = EnergyData(
            Power=power,
            Today=today,
            Total=0.0,
            Current=current,
            Voltage=voltage,
            Frequency=frequency,
        )
        _LOGGER.debug("EnergyData built: %s", data)
        return data

    def get_metrics_data(self) -> MetricsData:
        _LOGGER.debug("Building MetricsData …")
        pv_power = [self.get_state_float("pv1_power"), self.get_state_float("pv2_power")]
        pv_voltage = [self.get_state_float("pv1_voltage"), self.get_state_float("pv2_voltage")]
        pv_current = [self.get_state_float("pv1_current"), self.get_state_float("pv2_current")]
        load_power = [
            self.get_state_float("load_l1_power"),
            self.get_state_float("load_l2_power"),
            self.get_state_float("load_l3_power"),
        ]
        battery_soc = self.get_state_int("battery_soc")
        raw_batt_power = self.get_state_float("battery_power")
        battery_power = [abs(raw_batt_power)]
        battery_current = [abs(self.get_state_float("battery_current"))]
        battery_voltage = [self.get_state_float("battery_voltage")]
        grid_export_limit = self.get_state_float("export_limit_power", domain="number")
        battery_temperature = [self.get_state_float("battery_temperature")]
        inverter_temperature = self.get_state_float("radiator_temperature")

        data = MetricsData(
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
        _LOGGER.debug("MetricsData built: %s", data)
        return data
