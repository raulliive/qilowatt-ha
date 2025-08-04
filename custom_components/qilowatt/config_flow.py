import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_DEVICE_ID,
    CONF_INVERTER_ID,
    CONF_INVERTER_MODEL,
    CONF_MQTT_PASSWORD,
    CONF_MQTT_USERNAME,
    CONF_SUNSYNK_PREFIX,
    DOMAIN,
)


class QilowattConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Qilowatt Integration."""

    VERSION = 1

    def __init__(self) -> None:
        # Intermediate storage between steps
        self._initial_data: dict | None = None
        self._available_inverters: dict | None = None

    # ---------------------------------------------------------------------
    # STEP: USER
    # ---------------------------------------------------------------------
    async def async_step_user(self, user_input=None):
        """First step: credentials + inverter selection."""
        errors: dict[str, str] = {}

        if self._available_inverters is None:
            self._available_inverters = await self._discover_inverters()

        if not self._available_inverters:
            return self.async_abort(reason="no_inverters_found")

        if user_input is not None:
            selected_device_id: str = user_input[CONF_DEVICE_ID]
            model: str = self._available_inverters[selected_device_id][
                "inverter_integration"
            ]
            user_input[CONF_INVERTER_MODEL] = model

            if model == "Sunsynk":
                self._initial_data = user_input
                return await self.async_step_sunsynk_prefix()

            return self.async_create_entry(
                title=self._available_inverters[selected_device_id]["name"],
                data=user_input,
            )

        inverter_options = {
            device_id: inverter["name"]
            for device_id, inverter in self._available_inverters.items()
        }

        data_schema = vol.Schema(
            {
                vol.Required(CONF_MQTT_USERNAME): str,
                vol.Required(CONF_MQTT_PASSWORD): str,
                vol.Required(CONF_INVERTER_ID): str,
                vol.Required(CONF_DEVICE_ID): vol.In(inverter_options),
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    # ---------------------------------------------------------------------
    # STEP: SUNSYNK PREFIX
    # ---------------------------------------------------------------------
    async def async_step_sunsynk_prefix(self, user_input=None):
        """Second step (only for Sunsynk): ask for the prefix."""
        errors: dict[str, str] = {}

        if user_input is not None and self._initial_data is not None:
            final_data = {**self._initial_data, **user_input}
            selected_device_id = self._initial_data[CONF_DEVICE_ID]
            title = self._available_inverters[selected_device_id]["name"]
            self._initial_data = None
            return self.async_create_entry(title=title, data=final_data)

        data_schema = vol.Schema({vol.Required(CONF_SUNSYNK_PREFIX): str})
        return self.async_show_form(
            step_id="sunsynk_prefix", data_schema=data_schema, errors=errors
        )

    # ---------------------------------------------------------------------
    # DISCOVERY
    # ---------------------------------------------------------------------
    async def _discover_inverters(self):
        """Return a dict of detected inverters we know how to handle."""
        device_registry = dr.async_get(self.hass)
        inverters: dict[str, dict] = {}

        for device in device_registry.devices.values():
            # ---------- identifiers first ----------
            for ident in device.identifiers:
                # ident is a tuple of 1‑N strings; defend against short tuples
                domain_lower = str(ident[0]).lower() if len(ident) > 0 else ""
                dev_id_lower = str(ident[1]).lower() if len(ident) > 1 else ""

                if domain_lower == "mqtt" and "sa_inverter" in dev_id_lower:
                    inverters[device.id] = {
                        "name": device.name,
                        "inverter_integration": "SolarAssistant",
                    }
                elif domain_lower == "solarman":
                    inverters[device.id] = {
                        "name": device.name,
                        "inverter_integration": "Solarman",
                    }
                elif domain_lower == "solax_modbus":
                    inverters[device.id] = {
                        "name": device.name,
                        "inverter_integration": "Sofar",
                    }
                elif domain_lower == "huawei_solar":
                    inverters[device.id] = {
                        "name": device.name,
                        "inverter_integration": "Huawei",
                    }

            # ---------- heuristics outside identifier loop ----------
            name_lower = (device.name or "").lower()
            model_lower = (device.model or "").lower()

            if "deye" in name_lower and "esp32" in model_lower:
                inverters[device.id] = {
                    "name": device.name,
                    "inverter_integration": "EspHome",
                }

            # Generic Sunsynk detection: any element of any identifier contains "sunsynk"
            if any(
                "sunsynk" in str(part).lower()
                for ident in device.identifiers
                for part in ident
            ):
                inverters[device.id] = {
                    "name": device.name,
                    "inverter_integration": "Sunsynk",
                }

        return inverters
