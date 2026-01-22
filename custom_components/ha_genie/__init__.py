"""The HA Genie component."""
from .const import DOMAIN

async def async_setup(hass, config):
    """Set up the HA Genie component."""
    return True

async def async_setup_entry(hass, entry):
    """Set up HA Genie from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    
    async def handle_refresh(call):
        """Handle manual refresh service call."""
        # Find the coordinator in the sensors data (not ideal, better to store in hass.data[DOMAIN])
        # But we haven't stored the coordinator in hass.data[DOMAIN] yet. Let's fix that.
        # This is a common pattern:
        # coordinator = hass.data[DOMAIN][entry.entry_id]
        pass
        
    return True

async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return True
