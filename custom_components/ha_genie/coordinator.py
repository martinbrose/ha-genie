"""DataUpdateCoordinator for HA Genie."""
import logging
import json
import asyncio
from datetime import datetime, timedelta

import google.genai as genai
from google.genai import types

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.helpers import device_registry as dr

from .const import (
    DOMAIN, 
    CONF_GEMINI_API_KEY,
    CONF_GEMINI_MODEL,
    DEFAULT_GEMINI_MODEL,
    CONF_ENTITIES_TEMP,
    CONF_ENTITIES_ENERGY,
    CONF_ENTITIES_HUMIDITY,
    CONF_ENTITIES_RADON,
    CONF_ENTITIES_CO2,
    CONF_ENTITIES_VOC,
    CONF_ENTITIES_CONTACT,
    CONF_ENTITIES_VALVES,
    CONF_ENTITIES_GAS,
    CONF_UPDATE_FREQUENCY,
    FREQUENCY_DAILY,
    DEFAULT_UPDATE_FREQUENCY,
    CONF_DATA_AVERAGING,
    DATA_AVERAGING_HOURLY,
    DATA_AVERAGING_DAILY,
    DATA_AVERAGING_WEEKLY,
    DEFAULT_DATA_AVERAGING
)
from .data import aggregate_data, get_history_data

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=24)

class HAGenieCoordinator(DataUpdateCoordinator):
    """Coordinator to manage fetching data from history and Gemini."""

    def __init__(self, hass, config, api_key):
        """Initialize."""
        # Determine update interval
        frequency = config.get(CONF_UPDATE_FREQUENCY, DEFAULT_UPDATE_FREQUENCY)
        if frequency == FREQUENCY_DAILY:
            interval = timedelta(hours=24)
        else:
            # Default to Weekly
            interval = timedelta(days=7)
            
        super().__init__(
            hass,
            _LOGGER,
            name="HA Genie",
            update_interval=interval,
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
        
        # Determine averaging window
        averaging_inv = self.config.get(CONF_DATA_AVERAGING, DEFAULT_DATA_AVERAGING)
        if averaging_inv == DATA_AVERAGING_HOURLY:
             averaging_window = timedelta(hours=1)
        elif averaging_inv == DATA_AVERAGING_DAILY:
             averaging_window = timedelta(days=1)
        else:
             # Default to Weekly
             averaging_window = timedelta(days=7)
             
        _LOGGER.info("Sensor data averaging set to %s. Fetching 7 days history.", averaging_inv)
        
        # Always fetch 7 days of history, but bin it differently
        history_window = timedelta(days=7)
        history_data = await get_history_data(self.hass, all_entities, duration=history_window)
        aggregated_data = aggregate_data(self.hass, self.config, history_data, averaging_period=averaging_inv)
        
        payload_data = {k: v for k, v in aggregated_data.items() if k != "raw_sample_debug"}
        
        analysis_json = await self.call_gemini(payload_data)
        
        # Get Device ID for this config entry
        try:
            device_registry = dr.async_get(self.hass)
            device_entry = device_registry.async_get_device(identifiers={(DOMAIN, self.config.entry_id)})
            device_id = device_entry.id if device_entry else None
        except Exception as e:
            _LOGGER.warning("Could not find device for report event: %s", e)
            device_id = None
        
        # Fire an event that automations can listen to for notifications
        # Including device_id allows device triggers to filter correct events
        self.hass.bus.async_fire(f"{DOMAIN}_report_ready", {
            "summary": analysis_json.get("comparison", "Report Ready"),
            "status": analysis_json.get("status"),
            "alerts": len(analysis_json.get("bad_points", [])),
            "device_id": device_id
        })
        
        return {
            "analysis": analysis_json,
            "data": payload_data
        }

    async def call_gemini(self, data):
        """Call Google Gemini API using new SDK."""
        
        house_details = data.get('house_details', {})
        country = house_details.get('country', 'User Location')
        current_month = datetime.now().strftime("%B")
        
        # Get averaging period for context
        averaging_period = self.config.get(CONF_DATA_AVERAGING, DEFAULT_DATA_AVERAGING)
        
        prompt = f"""
        You are an expert home energy and health analyst.
        Analyse this weekly Home Assistant data for a {house_details.get('bedrooms')} bedroom, {house_details.get('size_sqm')} sqm home in {country} (unless specified otherwise in data).
        There are {house_details.get('residents', 2)} residents living in the home.
        Additional House Info: {house_details.get('info', 'None')}
        Current Month: {current_month}
        
        House Details: {house_details}
        Data Period: Last 7 Days
        Data Granularity: {averaging_period} Averaging
        
        Data: {json.dumps(data.get('sensor_aggregates', {}), indent=2)}
        
        IMPORTANT INSTRUCTIONS:
        1. You MUST heavily adjust benchmarks for the current month (currently {current_month}). 
           - For example, January gas consumption in the UK is typically 2.5-3.5x higher than summer levels.
           - Do NOT use a flat annual average broken down to weekly unless no seasonal data is available.
        2. Treat the following house information as authoritative and mandatory: {house_details.get('info', 'None')}.
           - If features like "electric underfloor heating" are present, explicitly cite them as reasons for higher consumption.
        
        Provide the output EXCLUSIVELY in valid JSON format with the following keys:
        - "status": (string) "Good", "Fair", or "Needs Attention"
        - "good_points": (list of strings) Key positive trends.
        - "bad_points": (list of strings) Issues or concerns.
        - "comparison": (string) detailed comparison text.
           - Compare against typical averages for **{country}** ADJUSTED for {current_month}.
           - Cite local energy authorities if possible (e.g. Ofgem for UK, EIA for US).
           - Always state when you are using seasonal adjustment.
           - Hedge statements: "estimated to be", "subject to variables", "indicative only", "seasonal estimate for {current_month}".
        - "suggestions": (list of strings) Actionable advice.
        
        Do not include markdown code blocks.
        """
        
        try:
            # new SDK call structure
            model_name = self.config.get(CONF_GEMINI_MODEL, DEFAULT_GEMINI_MODEL)
            
            # Ensure model name is bare (strip 'models/' prefix if user added it)
            if model_name.startswith("models/"):
                 model_name = model_name.replace("models/", "")
            
            _LOGGER.debug("Generated Prompt for Gemini: %s", prompt)
            _LOGGER.debug("Calling Gemini with model: %s", model_name)

            def _sync_call():
                return self.client.models.generate_content(
                    model=model_name,
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
