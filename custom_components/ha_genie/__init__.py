import logging
from .const import DOMAIN, CONF_GEMINI_API_KEY
from .coordinator import HAGenieCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass, config):
    """Set up the HA Genie component."""
    return True

async def async_setup_entry(hass, entry):
    """Set up HA Genie from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    api_key = entry.data.get(CONF_GEMINI_API_KEY)
    
    coordinator = HAGenieCoordinator(hass, entry.data, api_key)
    
    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()
    
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    
    async def handle_refresh(call):
        """Handle manual refresh service call."""
        _LOGGER.debug("Manual report generation triggered via service")
        # For simplicity, we trigger refresh on all loaded coordinators
        # In a multi-instance setup, you might want to specify which one, 
        # but for this singleton-like usage, refreshing all is fine.
        for coord in hass.data[DOMAIN].values():
             await coord.async_request_refresh()
        
    hass.services.async_register(DOMAIN, "generate_report", handle_refresh)
        
    return True

async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, ["sensor"]):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
