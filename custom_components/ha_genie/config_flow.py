"""Config flow for HA Genie integration."""
import logging
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_GEMINI_API_KEY,
    CONF_HOUSE_BEDROOMS,
    CONF_HOUSE_SIZE,
    CONF_HOUSE_COUNTRY,
    CONF_ENTITIES_TEMP,
    CONF_ENTITIES_HUMIDITY,
    CONF_ENTITIES_RADON,
    CONF_ENTITIES_CO2,
    CONF_ENTITIES_VOC,
    CONF_ENTITIES_CONTACT,
    CONF_ENTITIES_VALVES,
    CONF_ENTITIES_ENERGY,
    CONF_ENTITIES_GAS,
    DEFAULT_HOUSE_BEDROOMS,
    DEFAULT_HOUSE_SIZE,
    DEFAULT_HOUSE_COUNTRY,
    CONF_HOUSE_RESIDENTS,
    DEFAULT_HOUSE_RESIDENTS,
    CONF_HOUSE_INFO,
    CONF_GEMINI_MODEL,
    DEFAULT_GEMINI_MODEL,
    CONF_UPDATE_FREQUENCY,
    FREQUENCY_DAILY,
    FREQUENCY_WEEKLY,
    DEFAULT_UPDATE_FREQUENCY,
)

_LOGGER = logging.getLogger(__name__)

class HAGenieConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HA Genie."""

    VERSION = 1

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        """Handle the initial step."""
        errors = {}
        
        if user_input is not None:
            # Validate input if needed (e.g. check API key format lightly)
            if not user_input.get(CONF_GEMINI_API_KEY):
                errors["base"] = "missing_api_key"
            else:
                _LOGGER.debug("Config flow user input: %s", user_input)
                return self.async_create_entry(title="HA Genie", data=user_input)

        # Schema for user input
        data_schema = vol.Schema({
            vol.Required(CONF_GEMINI_API_KEY): cv.string,
            vol.Required(CONF_GEMINI_MODEL, default=DEFAULT_GEMINI_MODEL): cv.string,
            vol.Required(CONF_HOUSE_BEDROOMS, default=DEFAULT_HOUSE_BEDROOMS): int,
            vol.Required(CONF_HOUSE_SIZE, default=DEFAULT_HOUSE_SIZE): int,
            vol.Required(CONF_HOUSE_COUNTRY, default="UK"): cv.string,
            vol.Required(CONF_HOUSE_RESIDENTS, default=DEFAULT_HOUSE_RESIDENTS): int,
            vol.Optional(CONF_HOUSE_INFO): cv.string,
            vol.Required(CONF_UPDATE_FREQUENCY, default=DEFAULT_UPDATE_FREQUENCY): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[FREQUENCY_DAILY, FREQUENCY_WEEKLY],
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
            
            # Entity Selectors
            vol.Optional(CONF_ENTITIES_TEMP): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", multiple=True)
            ),
            vol.Optional(CONF_ENTITIES_HUMIDITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="humidity", multiple=True)
            ),
            vol.Optional(CONF_ENTITIES_RADON): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", multiple=True)
            ),
            vol.Optional(CONF_ENTITIES_CO2): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="carbon_dioxide", multiple=True)
            ),
            vol.Optional(CONF_ENTITIES_VOC): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor", "binary_sensor", "climate", "air_quality", "utility_meter"], multiple=True)
            ),
            vol.Optional(CONF_ENTITIES_CONTACT): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="binary_sensor", device_class=["door", "window"], multiple=True)
            ),
            vol.Optional(CONF_ENTITIES_VALVES): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="climate", multiple=True)
            ),
            vol.Optional(CONF_ENTITIES_ENERGY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="energy", multiple=True)
            ),
            vol.Optional(CONF_ENTITIES_GAS): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor", "binary_sensor", "climate", "air_quality", "utility_meter"], multiple=True)
            ),
        })

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return HAGenieOptionsFlowHandler(config_entry)


class HAGenieOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for HA Genie."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        # self.config_entry is set by base class, cannot be assigned to
        _LOGGER.debug("Options flow initialised for entry %s", config_entry.entry_id)

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
             _LOGGER.debug("Options flow user input: %s", user_input)
             # Update the main config entry with the new data
             self.hass.config_entries.async_update_entry(self.config_entry, data=user_input)
             # Reload the integration to pick up changes immediately
             await self.hass.config_entries.async_reload(self.config_entry.entry_id)
             return self.async_create_entry(title="", data={})

        # Allow updating the configuration
        current_config = self.config_entry.data
        
        # Helper to get default
        def get_default(key, fallback=None):
            return current_config.get(key, fallback)

        data_schema = vol.Schema({
            vol.Required(CONF_GEMINI_API_KEY, default=get_default(CONF_GEMINI_API_KEY)): cv.string,
            vol.Required(CONF_GEMINI_MODEL, default=get_default(CONF_GEMINI_MODEL, DEFAULT_GEMINI_MODEL)): cv.string,
            vol.Required(CONF_HOUSE_BEDROOMS, default=get_default(CONF_HOUSE_BEDROOMS, 3)): int,
            vol.Required(CONF_HOUSE_SIZE, default=get_default(CONF_HOUSE_SIZE, 150)): int,
            vol.Required(CONF_HOUSE_COUNTRY, default=get_default(CONF_HOUSE_COUNTRY, "UK")): cv.string,
            vol.Required(CONF_HOUSE_RESIDENTS, default=get_default(CONF_HOUSE_RESIDENTS, DEFAULT_HOUSE_RESIDENTS)): int,
            vol.Optional(CONF_HOUSE_INFO, default=get_default(CONF_HOUSE_INFO, "")): cv.string,
            vol.Required(CONF_UPDATE_FREQUENCY, default=get_default(CONF_UPDATE_FREQUENCY, DEFAULT_UPDATE_FREQUENCY)): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[FREQUENCY_DAILY, FREQUENCY_WEEKLY],
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
            
            vol.Optional(CONF_ENTITIES_TEMP, default=get_default(CONF_ENTITIES_TEMP, [])): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", multiple=True)
            ),
            vol.Optional(CONF_ENTITIES_HUMIDITY, default=get_default(CONF_ENTITIES_HUMIDITY, [])): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="humidity", multiple=True)
            ),
            vol.Optional(CONF_ENTITIES_RADON, default=get_default(CONF_ENTITIES_RADON, [])): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", multiple=True)
            ),
            vol.Optional(CONF_ENTITIES_CO2, default=get_default(CONF_ENTITIES_CO2, [])): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="carbon_dioxide", multiple=True)
            ),
            vol.Optional(CONF_ENTITIES_VOC, default=get_default(CONF_ENTITIES_VOC, [])): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor", "binary_sensor", "climate", "air_quality", "utility_meter"], multiple=True)
            ),
            vol.Optional(CONF_ENTITIES_CONTACT, default=get_default(CONF_ENTITIES_CONTACT, [])): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="binary_sensor", device_class=["door", "window"], multiple=True)
            ),
            vol.Optional(CONF_ENTITIES_VALVES, default=get_default(CONF_ENTITIES_VALVES, [])): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="climate", multiple=True)
            ),
            vol.Optional(CONF_ENTITIES_ENERGY, default=get_default(CONF_ENTITIES_ENERGY, [])): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="energy", multiple=True)
            ),
            vol.Optional(CONF_ENTITIES_GAS, default=get_default(CONF_ENTITIES_GAS, [])): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor", "binary_sensor", "climate", "air_quality", "utility_meter"], multiple=True)
            ),
        })

        return self.async_show_form(
            step_id="user", 
            data_schema=data_schema,
            description_placeholders={"warning": "Changing entities will reload the integration."}
        )
