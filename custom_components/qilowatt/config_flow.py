import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
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
        # Hold data between steps when we need an extra prompt for Sunsynk
        self._initial_data: dict | None = None
        self._available_inverters: dict | None = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if self._available_inverters is None:
            self._available_inverters = await self._discover_inverters()

        if user_input is not None:
            selected_device_id = user_input[CONF_DEVICE_ID]
            model = self._available_inverters[selected_device_id]["inverter_integration"]

            # Attach the detected inverter model
            user_input[CONF_INVERTER_MODEL] = model

            # If Sunsynk, ask for the prefix in a follow-up step
            if model == "Sunsynk":
                self._initial_data = user_input
                return await self.async_step_sunsynk_prefix()

            # Otherwise we can finish immediately
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

    async def async_step_sunsynk_prefix(self, user_input=None):
        """Ask for the Sunsynk prefix when the inverter model is Sunsynk."""
        errors = {}
        if user_input is not None and self._initial_data is not None:
            # Merge the two steps' data and finish
            final_data = {**self._initial_data, **user_input}
            selected_device_id = self._initial_data[CONF_DEVICE_ID]
            title = self._available_inverters[selected_device_id]["name"]
            # Clear temp state
            self._initial_data = None
            return self.async_create_entry(title=title, data=final_data)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_SUNSYNK_PREFIX): str,
            }
        )
        return self.async_show_form(step_id="sunsynk_prefix", data_schema=data_schema, errors=errors)

    async def _discover_inverters(self):
        """Discover inverters in Home Assistant."""
        device_registry = dr.async_get(self.hass)
        inverters = {}

        for device in device_registry.devices.values():
            for identifier in device.identifiers:
                domain, device_id, *_ = identifier
                if domain == "mqtt":
                    # Solar Assistant inverter
                    if "sa_inverter" in device_id:
                        inverters[device.id] = {
                            "name": device.name,
                            "inverter_integration": "SolarAssistant",
                        }
                if domain == "solarman":
                    inverters[device.id] = {
                        "name": device.name,
                        "inverter_integration": "Solarman",
                    }
                if domain == "solax_modbus":
                    inverters[device.id] = {
                        "name": device.name,
                        "inverter_integration": "Sofar",
                    }
                if domain == "huawei_solar":
                    inverters[device.id] = {
                        "name": device.name,
                        "inverter_integration": "Huawei",
                    }

            # Heuristics outside the identifier loop
            if "Deye" in (device.name or "") and "esp32" in (device.model or ""):
                inverters[device.id] = {
                    "name": device.name,
                    "inverter_integration": "EspHome",
                }
            # If you rely on a specific domain/id for the Sunsynk add-on, adapt this check:
            if any(d == "hass-addon-sunsynk-multi" for d, *_ in device.identifiers):
                inverters[device.id] = {
                    "name": device.name,
                    "inverter_integration": "Sunsynk",
                }

        return inverters
