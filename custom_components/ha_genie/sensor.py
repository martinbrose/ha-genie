"""Sensor platform for HA Genie."""
import logging
import json
import asyncio
from datetime import timedelta
import voluptuous as vol

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.core import callback

from .const import (
    DOMAIN, 
    CONF_GEMINI_API_KEY,
    CONF_ENTITIES_TEMP,
    CONF_ENTITIES_ENERGY,
    CONF_ENTITIES_HUMIDITY,
    CONF_ENTITIES_RADON,
    CONF_ENTITIES_CO2,
    CONF_ENTITIES_VOC,
    CONF_ENTITIES_CONTACT,
    CONF_ENTITIES_VALVES,
    CONF_ENTITIES_GAS
)
from .data import aggregate_data, get_history_data

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=24)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the HA Genie sensors."""
    api_key = config_entry.data.get(CONF_GEMINI_API_KEY)
    
    coordinator = HAGenieCoordinator(hass, config_entry.data, api_key)
    
    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()
    
    async_add_entities([
        HAGenieSummarySensor(coordinator),
        HAGenieInsightsSensor(coordinator),
        HAGenieAlertsSensor(coordinator)
    ], True)


class HAGenieCoordinator(DataUpdateCoordinator):
    """Coordinator to manage fetching data from history and Gemini."""

    def __init__(self, hass, config, api_key):
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name="HA Genie",
            update_interval=SCAN_INTERVAL,
        )
        self.config = config
        self.api_key = api_key
        
        # Configure the SDK
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-pro')

    async def _async_update_data(self):
        """Fetch data and call Gemini."""
        
        all_entities = []
        for key in [
            CONF_ENTITIES_TEMP, CONF_ENTITIES_ENERGY, CONF_ENTITIES_HUMIDITY,
            CONF_ENTITIES_RADON, CONF_ENTITIES_CO2, CONF_ENTITIES_VOC,
            CONF_ENTITIES_CONTACT, CONF_ENTITIES_VALVES, CONF_ENTITIES_GAS
        ]: 
             all_entities.extend(self.config.get(key, []) or [])
        
        history_data = await get_history_data(self.hass, all_entities, days=7)
        aggregated_data = aggregate_data(self.hass, self.config, history_data)
        
        payload_data = {k: v for k, v in aggregated_data.items() if k != "raw_sample_debug"}
        
        analysis_json = await self.call_gemini(payload_data)
        
        # Fire an event that automations can listen to for notifications
        self.hass.bus.async_fire(f"{DOMAIN}_report_ready", {
            "summary": analysis_json.get("comparison", "Report Ready"),
            "status": analysis_json.get("status"),
            "alerts": len(analysis_json.get("bad_points", []))
        })
        
        return {
            "analysis": analysis_json,
            "data": payload_data
        }

    async def call_gemini(self, data):
        """Call Google Gemini API using SDK."""
        
        house_details = data.get('house_details', {})
        country = house_details.get('country', 'User Location')
        
        prompt = f"""
        You are an expert home energy and health analyst.
        Analyse this weekly Home Assistant data for a 3-bedroom, 150 sqm home in {country} (unless specified otherwise in data).
        
        House Details: {house_details}
        Data (Weekly Aggregates): {json.dumps(data.get('sensor_aggregates', {}), indent=2)}
        
        Provide the output EXCLUSIVELY in valid JSON format with the following keys:
        - "status": (string) "Good", "Fair", or "Needs Attention"
        - "good_points": (list of strings) Key positive trends (e.g., "Stable 18-21°C temperatures").
        - "bad_points": (list of strings) Issues or concerns (e.g., "High humidity >60% risking mould").
        - "comparison": (string) detailed comparison text.
           Compare against typical averages for **{country}**.
           Cite local energy authorities if possible (e.g. Ofgem for UK, EIA for US, etc.).
           Verify numerical comparisons carefully. 
           Consider regional exceptions.
           Hedge statements: "estimated to be", "subject to variables", "indicative only".
        - "suggestions": (list of strings) Actionable advice.
        
        Do not include markdown code blocks.
        """
        
        try:
            response = await self.hass.async_add_executor_job(
                self.model.generate_content, 
                prompt
            )
            text = response.text.strip()
            
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
                
            return json.loads(text)
            
        except Exception as e:
            _LOGGER.error(f"Gemini API Error: {e}")
            # Return a valid fallback structure so sensors don't crash hard
            return {
                "status": "Error",
                "good_points": [],
                "bad_points": [f"API Error: {str(e)}"],
                "comparison": "Analysis failed.",
                "suggestions": []
            }


class HAGenieBaseSensor(SensorEntity):
    """Base class for HA Genie sensors."""
    
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_has_entity_name = True

    @property
    def available(self):
        return self.coordinator.last_update_success

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
    
    async def async_update(self):
        """Update the sensor."""
        await self.coordinator.async_request_refresh()


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
