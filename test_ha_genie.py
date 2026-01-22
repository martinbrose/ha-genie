"""Test script for HA Genie component logic."""
import asyncio
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta
import json

# Modify sys.path or structure to import local modules if needed, 
# but assuming we run this from the parent dir or use relative imports carefully.
# For simplicity in this environment, I will mock the HA imports heavily.

import sys
import os

# Mock HA modules before importing local modules
sys.modules['homeassistant'] = MagicMock()
sys.modules['homeassistant.core'] = MagicMock()
sys.modules['homeassistant.components.sensor'] = MagicMock()
sys.modules['homeassistant.helpers.update_coordinator'] = MagicMock()
# Ensure DataUpdateCoordinator is a class we can inherit from without weird MagicMock behavior
class MockCoordinator:
    def __init__(self, hass, logger, name, update_interval):
        self.hass = hass
        self.last_update_success = True
        self.data = None
sys.modules['homeassistant.helpers.update_coordinator'].DataUpdateCoordinator = MockCoordinator
sys.modules['homeassistant.util'] = MagicMock()
sys.modules['homeassistant.util.dt'] = MagicMock()
sys.modules['google'] = MagicMock()
sys.modules['google.genai'] = MagicMock()
sys.modules['google.api_core'] = MagicMock()
sys.modules['google.api_core.exceptions'] = MagicMock()
sys.modules['voluptuous'] = MagicMock()

# Now import the local modules
# We need to set up the path to find custom_components
sys.path.append(os.getcwd())

from custom_components.ha_genie.data import aggregate_data
from custom_components.ha_genie.sensor import HAGenieCoordinator
from custom_components.ha_genie.const import *

class MockState:
    def __init__(self, state, last_updated=None, attributes=None):
        self.state = state
        self.last_updated = last_updated or datetime.now()
        self.attributes = attributes or {}

class TestHAGenie(unittest.TestCase):
    
    def test_aggregation(self):
        """Test that data aggregation works and handles privacy."""
        hass = MagicMock()
        
        config = {
            CONF_HOUSE_BEDROOMS: 3,
            CONF_HOUSE_SIZE: 150,
            CONF_HOUSE_COUNTRY: "UK",
            CONF_ENTITIES_TEMP: ["sensor.temp"],
            CONF_ENTITIES_ENERGY: ["sensor.energy"],
            CONF_ENTITIES_CONTACT: ["binary_sensor.door"]
        }
        
        # Mock History Data
        # Temp: 18, 20, 22 -> Avg 20
        # Energy: 100, 110, 150 -> Usage 50
        # Door: off, on, off, on -> Count 2
        
        history_data = {
            "sensor.temp": [MockState("18"), MockState("20"), MockState("22")],
            "sensor.energy": [MockState("100"), MockState("110"), MockState("150")],
            "binary_sensor.door": [MockState("off"), MockState("on"), MockState("off"), MockState("on")]
        }
        
        summary = aggregate_data(hass, config, history_data)
        
        # Check Structure
        self.assertEqual(summary["house_details"]["bedrooms"], 3)
        
        # Check Aggregates
        self.assertAlmostEqual(summary["sensor_aggregates"]["temperature_avg"]["sensor.temp"], 20.0)
        self.assertAlmostEqual(summary["sensor_aggregates"]["electricity_usage_kwh"]["sensor.energy"], 50.0)
        self.assertEqual(summary["sensor_aggregates"]["contact_openings_count"]["binary_sensor.door"], 2)
        
        # Check Debug Field Exists (It should be in aggregate_data output, but removed before API call)
        self.assertIn("raw_sample_debug", summary)

class TestCoordinator(unittest.IsolatedAsyncioTestCase):
    
    async def test_api_call_structure_and_privacy(self):
        """Test that the coordinator removes debug data and calls API correctly."""
        hass = MagicMock()
        config = {
            CONF_GEMINI_API_KEY: "fake_key",
            CONF_ENTITIES_TEMP: ["sensor.temp"]
        }
        
        coordinator = HAGenieCoordinator(hass, config, "fake_key")
        
        # Mock get_history_data (since we can't easily mock the import inside sensor.py without more patching)
        # We will patch the method on the class or instance? 
        # Easier to patch 'custom_components.ha_genie.sensor.get_history_data'
        
        # Use AsyncMock for the history function since it is awaited
        with patch('custom_components.ha_genie.sensor.get_history_data', new_callable=AsyncMock) as mock_history, \
             patch('google.genai.Client') as MockClient:
            
            # Setup Mock History
            mock_history.return_value = {
                "sensor.temp": [MockState("20")]
            }
            
            # Setup Mock Model Response
            mock_response = MagicMock()
            mock_response.text = json.dumps({
                "status": "Good",
                "good_points": ["Nice temp"],
                "bad_points": [],
                "comparison": "Average",
                "suggestions": []
            })
            
            # Setup Client Mock
            mock_client_instance = MockClient.return_value
            # For the coordinator to pick up our mock client, we might need to patch where it's instantiated
            # or mock the genai.Client constructor.
            # We patched 'google.genai.Client' so when h_a_g.sensor imports and calls Client(), it gets our mock.
            # inside sensor: self.client = genai.Client(...)
            
            # The code calls: self.client.models.generate_content(...)
            # So we need mock_client_instance.models.generate_content to be what matches the executor call target?
            # Actually, executor calls the function.
            
            # Let's verify what we are patching.
            # In sensor.py: import google.genai as genai -> genai.Client
            
            # We need to ensure that the coordinator uses our mock client.
            # Since we are testing logic inside coordinator that we instantiate:
            coordinator = HAGenieCoordinator(hass, config, "fake_key")
            # But wait, coordinator init calls genai.Client
            # So we need to patch it BEFORE init or patch it globally for the module.
            # The context manager above does patch it globally in the scope of `with`.
            # But we instantiated coordinator BEFORE the `with` block in the previous code structure!
            pass # placeholder for logic adjustment
            
            # Move coordinator init INSIDE the patch block
            coordinator = HAGenieCoordinator(hass, config, "fake_key")

            # hass.async_add_executor_job is awaited. It needs to be an async mock or return a future
            
            captured_args = []
            async def fake_executor_job(target, *args, **kwargs):
                captured_args.append((target, args, kwargs))
                return mock_response
            
            hass.async_add_executor_job = fake_executor_job

            # Run Update
            result = await coordinator._async_update_data()
            
            # VERIFY PRIVACY: Check what was passed to generate_content
            # captured_args[0] is (target, args, kwargs)
            # prompt is now in kwargs['contents']
            # Let's check what was captured
            actual_call = captured_args[0]
            kwargs_sent = actual_call[2]
            prompt_sent = kwargs_sent.get('contents')
            
            # If prompt wasn't in kwargs, check positional args (though we used keyword in sensor.py)
            if not prompt_sent and actual_call[1]:
                 prompt_sent = actual_call[1][0]
            
            self.assertNotIn("raw_sample_debug", prompt_sent)
            self.assertIn("temperature_avg", prompt_sent)
            
            # VERIFY RESULT
            self.assertEqual(result["analysis"]["status"], "Good")
            self.assertEqual(result["analysis"]["good_points"], ["Nice temp"])

if __name__ == '__main__':
    unittest.main()
