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

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        available_inverters = await self._discover_inverters()
        if user_input is not None:
            # Validate the input here if needed
            if user_input is not None:
                selected_device_id = user_input["device_id"]
                user_input[CONF_INVERTER_MODEL] = available_inverters[
                    selected_device_id
                ]["inverter_integration"]

            # If SunSynk, go to a second step to collect the prefix
            if available_inverters[selected_device_id]["inverter_integration"].lower() == "sunsynk":
                # Stash data between steps
                self._staged_input = user_input
                self._staged_inverters = available_inverters
                return await self.async_step_sunsynk_prefix()

            # Otherwise finish immediately
                
                return self.async_create_entry(
                    title=f"{available_inverters[selected_device_id]['name']}",
                    data=user_input,
                )

        inverter_options = {
            device_id: inverter["name"]
            for device_id, inverter in available_inverters.items()
        }

        data_schema = vol.Schema(
            {
                vol.Required(CONF_MQTT_USERNAME): str,
                vol.Required(CONF_MQTT_PASSWORD): str,
                vol.Required(CONF_INVERTER_ID): str,
                vol.Required(CONF_DEVICE_ID): vol.In(inverter_options),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

        async def async_step_sunsynk_prefix(self, user_input=None):
        """Ask for SunSynk-specific prefix."""
        errors = {}

        if user_input is not None:
            prefix = (user_input.get(CONF_SUNSYNK_PREFIX) or "").strip()
            if not prefix:
                errors[CONF_SUNSYNK_PREFIX] = "required"
            else:
                # Merge and finish
                data = dict(self._staged_input)
                data[CONF_SUNSYNK_PREFIX] = prefix
                selected_device_id = data["device_id"]
                title = self._staged_inverters[selected_device_id]["name"]
                return self.async_create_entry(title=title, data=data)

        schema = vol.Schema({vol.Required(CONF_SUNSYNK_PREFIX): str})
        return self.async_show_form(step_id="sunsynk_prefix", data_schema=schema, errors=errors)


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
                    # Solarman inverter integration
                    inverters[device.id] = {
                        "name": device.name,
                        "inverter_integration": "Solarman",
                    }
                    if device.manufacturer == "Sofar":
                        # Solarman Sofar inverter integration
                        inverters[device.id] = {
                            "name": device.name,
                            "inverter_integration": "SolarmanSofar",
                        }
                if domain == "solax_modbus":
                    # Sofar Modbus inverter integration
                    inverters[device.id] = {
                        "name": device.name,
                        "inverter_integration": "Sofar",
                    }
                if domain == "huawei_solar":
                    # Huawei inverter integration
                    inverters[device.id] = {
                        "name": device.name,
                        "inverter_integration": "Huawei",
                    }
                if domain == "victron_qw_addon":
                    # Victron inverter integration
                    inverters[device.id] = {
                        "name": device.name or device_id,
                        "inverter_integration": "Victron",
                    }
            if (device.name and "Deye" in device.name) and (device.model and "esp32" in device.model):
                inverters[device.id] = {
                    "name": device.name,
                    "inverter_integration": "EspHome",
                }

      # --- SunSynk detection (identifiers only, case-insensitive) ---
            if any(
                    "sunsynk" in "|".join(str(part).lower() for part in ident)
                    for ident in device.identifiers
                ):
                    inverters[device.id] = {
                        "name": device.name or "Sunsynk",
                        "inverter_integration": "Sunsynk",
            }
        return inverters
