"""Sensor platform for HA Genie."""
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the HA Genie sensors."""
    # Coordinator is now initialized in __init__.py
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    async_add_entities([
        HAGenieSummarySensor(coordinator),
        HAGenieInsightsSensor(coordinator),
        HAGenieAlertsSensor(coordinator)
    ], True)


from homeassistant.helpers.update_coordinator import CoordinatorEntity

class HAGenieBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for HA Genie sensors."""
    
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_has_entity_name = True

    # CoordinatorEntity handles available, async_added_to_hass, and should_poll=False automatically
    # We do NOT implement async_update, as that would cause polling loops.


class HAGenieSummarySensor(HAGenieBaseSensor):
    """Main summary sensor."""
    
    _attr_name = "Genie Summary"
    _attr_unique_id = "ha_genie_summary"
    _attr_icon = "mdi:creation"

    @property
    def native_value(self):
        if self.coordinator.data:
            return self.coordinator.data["analysis"].get("status", "Unknown")
        return "Initializing"

    @property
    def extra_state_attributes(self):
        if self.coordinator.data:
            return self.coordinator.data["analysis"]
        return {}


class HAGenieInsightsSensor(HAGenieBaseSensor):
    """Sensor for positive insights/trends."""
    
    _attr_name = "Genie Insights"
    _attr_unique_id = "ha_genie_insights"
    _attr_icon = "mdi:thumb-up-outline"

    @property
    def native_value(self):
        if self.coordinator.data:
            count = len(self.coordinator.data["analysis"].get("good_points", []))
            return f"{count} Trends"
        return "0 Trends"

    @property
    def extra_state_attributes(self):
        if self.coordinator.data:
            return {
                "insights": self.coordinator.data["analysis"].get("good_points", []),
                "suggestions": self.coordinator.data["analysis"].get("suggestions", [])
            }
        return {}


class HAGenieAlertsSensor(HAGenieBaseSensor):
    """Sensor for alerts/issues."""
    
    _attr_name = "Genie Alerts"
    _attr_unique_id = "ha_genie_alerts"
    _attr_icon = "mdi:alert-circle-outline"

    @property
    def native_value(self):
        if self.coordinator.data:
            count = len(self.coordinator.data["analysis"].get("bad_points", []))
            return f"{count} Alerts"
        return "0 Alerts"

    @property
    def extra_state_attributes(self):
        if self.coordinator.data:
            return {
                "alerts": self.coordinator.data["analysis"].get("bad_points", [])
            }
        return {}
