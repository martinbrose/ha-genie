"""DataUpdateCoordinator for HA Genie."""
import logging
import json
import asyncio
from datetime import timedelta

import google.genai as genai
from google.genai import types

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

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
        
        # Configure the SDK (New Syntax)
        self.client = genai.Client(api_key=self.api_key)

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
        """Call Google Gemini API using new SDK."""
        
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
            # new SDK call structure
            # model='gemini-2.0-flash' is a good default for the next gen SDK
            
            def _sync_call():
                _LOGGER.debug("Starting Gemini API call with model gemini-2.0-flash")
                return self.client.models.generate_content(
                    model='gemini-2.0-flash',
                    contents=prompt
                )

            response = await self.hass.async_add_executor_job(_sync_call)
            
            if hasattr(response, 'text'):
                 _LOGGER.debug("Gemini response received: %s", response.text[:200])
            
            # SDK should return an object where .text is the response content
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
