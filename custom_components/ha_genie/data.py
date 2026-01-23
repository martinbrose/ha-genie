"""Data aggregation helpers for HA Genie."""
import logging
from datetime import timedelta
import statistics
from typing import Any, Dict, List, Optional

from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util
# Attempt to import history, handling potential changes in HA core versions
try:
    from homeassistant.components.recorder import history
    from homeassistant.components.recorder import get_instance
except ImportError:
    # Fallback or mock for environments where full recorder isn't available
    history = None

from .const import (
    CONF_ENTITIES_TEMP,
    CONF_ENTITIES_HUMIDITY,
    CONF_ENTITIES_RADON,
    CONF_ENTITIES_CO2,
    CONF_ENTITIES_VOC,
    CONF_ENTITIES_CONTACT,
    CONF_ENTITIES_VALVES,
    CONF_ENTITIES_ENERGY,
    CONF_ENTITIES_GAS,
    CONF_HOUSE_BEDROOMS,
    CONF_HOUSE_SIZE,
    CONF_HOUSE_SIZE,
    CONF_HOUSE_COUNTRY,
    CONF_HOUSE_RESIDENTS,
    CONF_HOUSE_INFO,
    DATA_AVERAGING_HOURLY,
    DATA_AVERAGING_DAILY,
    DATA_AVERAGING_WEEKLY
)

_LOGGER = logging.getLogger(__name__)

async def get_history_data(hass: HomeAssistant, entity_ids: List[str], duration: timedelta = timedelta(days=7)) -> Dict[str, List[State]]:
    """Fetch history data for a list of entities over the specified duration.
    
    Returns a dictionary mapping entity_id to a list of State objects.
    """
    if not entity_ids:
        return {}

    start_time = dt_util.utcnow() - duration
    end_time = dt_util.utcnow()
    
    if history is None:
         _LOGGER.error("Recorder history module not available.")
         return {}

    # Use history.get_significant_states which is the standard API
    # include_start_time_state=True ensures we have a starting point
    return await hass.async_add_executor_job(
        history.get_significant_states,
        hass,
        start_time,
        end_time,
        entity_ids,
        None, # filters
        True, # include_start_time_state
        True, # significant_changes_only
        False # minimal_response
    )

def calculate_mean(states: List[State]) -> Optional[float]:
    """Calculate the mean value from a list of states."""
    values = []
    for state in states:
        try:
            if state.state not in ("unknown", "unavailable"):
                values.append(float(state.state))
        except ValueError:
            pass
    
    if not values:
        return None
    return statistics.mean(values)

def calculate_usage(states: List[State]) -> Optional[float]:
    """Calculate usage (max - min) for increasing counters like energy."""
    values = []
    for state in states:
        try:
            if state.state not in ("unknown", "unavailable"):
                values.append(float(state.state))
        except ValueError:
            pass
    
    if not values:
        return None
    
    # Simple difference for total increasing counter
    # Handle resets? For now simple max-min
    return max(values) - min(values)

def calculate_on_count(states: List[State]) -> int:
    """Calculate how many times a binary sensor turned 'on' (or 'open')."""
    count = 0
    # Simple transition counting
    # This counts every time the state is 'on' in the history list.
    # Note: History returns state changes.
    for state in states:
        if state.state in ("on", "open"):
             count += 1
    return count

def calculate_attribute_mean(states: List[State], attribute: str) -> Optional[float]:
    """Calculate mean of a specific attribute (e.g. current_temperature for climate)."""
    values = []
    for state in states:
        try:
            val = state.attributes.get(attribute)
            if val is not None:
                values.append(float(val))
        except (ValueError, TypeError):
            pass
            
    if not values:
        return None
    return statistics.mean(values)


def aggregate_data(hass: HomeAssistant, config: Dict[str, Any], history_data: Dict[str, List[State]], averaging_period: str = DATA_AVERAGING_WEEKLY) -> Dict[str, Any]:
    """Aggregate raw history data into a summary JSON structure."""
    
    summary = {
        "period_days": 7, # This remains the fetch window
        "averaging_period": averaging_period,
        "house_details": {
            "bedrooms": config.get(CONF_HOUSE_BEDROOMS),
            "size_sqm": config.get(CONF_HOUSE_SIZE),
            "residents": config.get(CONF_HOUSE_RESIDENTS),
            "info": config.get(CONF_HOUSE_INFO),
            "country": config.get(CONF_HOUSE_COUNTRY),
        },
        "sensor_aggregates": {},
        "raw_sample_debug": {} # Kept for user request "Output sample JSON structure", normally wouldn't send to API if GDPR strict
    }
    
    # Determine binning interval
    bin_interval = None
    if averaging_period == DATA_AVERAGING_HOURLY:
        bin_interval = timedelta(hours=1)
    elif averaging_period == DATA_AVERAGING_DAILY:
        bin_interval = timedelta(days=1)
    
    # Calculate global start/end for binning (approximate based on data or now)
    end_time = dt_util.utcnow()
    start_time = end_time - timedelta(days=7) # Fixed 7 days window for now
    
    # Helper to process a category
    def process_category(category_key: str, entity_ids: List[str], calc_func):
        if not entity_ids:
            return
        
        category_data = {}
        for entity_id in entity_ids:
            states = history_data.get(entity_id, [])
            
            # Fallback to current state if no history
            if not states:
                state = hass.states.get(entity_id)
                if state:
                    states = [state]
            
            if states:
                # 1. Store debug sample
                summary["raw_sample_debug"][entity_id] = [
                    {"state": s.state, "time": s.last_updated.isoformat()} 
                    for s in states[:5]
                ]

                # 2. Calculate values
                if bin_interval:
                    # Granular Output (List of values)
                    bins = bin_history_data(states, start_time, end_time, bin_interval)
                    binned_values = []
                    for b in bins:
                        val = calc_func(b["states"])
                        if val is not None:
                            # Clean timestamp for JSON (remove +00:00 for brevity if needed, but ISO is safer)
                            binned_values.append({
                                "start": b["start"], 
                                "value": round(val, 2)
                            })
                    if binned_values:
                         category_data[entity_id] = binned_values
                else:
                    # Single Aggregate Output (Backward compatible / Weekly)
                    val = calc_func(states)
                    if val is not None:
                        category_data[entity_id] = round(val, 2)
                    

        if category_data:
            summary["sensor_aggregates"][category_key] = category_data

    # 1. Averages (Temp, Humidity, Radon, CO2, VOC)
    process_category("temperature_avg", config.get(CONF_ENTITIES_TEMP, []), calculate_mean)
    process_category("humidity_avg", config.get(CONF_ENTITIES_HUMIDITY, []), calculate_mean)
    process_category("radon_avg_bq_m3", config.get(CONF_ENTITIES_RADON, []), calculate_mean)
    process_category("co2_avg_ppm", config.get(CONF_ENTITIES_CO2, []), calculate_mean)
    process_category("voc_avg_ppb", config.get(CONF_ENTITIES_VOC, []), calculate_mean)

    # 2. Usage (Energy, Gas)
    process_category("electricity_usage_kwh", config.get(CONF_ENTITIES_ENERGY, []), calculate_usage)
    process_category("gas_usage_kwh", config.get(CONF_ENTITIES_GAS, []), calculate_usage)
    
    # 3. Contact Sensors (Count openings)
    process_category("contact_openings_count", config.get(CONF_ENTITIES_CONTACT, []), calculate_on_count)
    
    # 4. Radiator Valves (Average Current Temp)
    climate_entities = config.get(CONF_ENTITIES_VALVES, [])
    if climate_entities:
        c_data = {}
        for entity_id in climate_entities:
            states = history_data.get(entity_id, [])
            if not states:
                 state = hass.states.get(entity_id)
                 if state: states = [state]
            if states:
                 # Logic for climate binning is the same structure, just different extraction func
                 pass # TODO: Refactor process_category to handle custom calc_func better or CP logic.
                 # For now, let's keep it simple and just do Weekly/Single average for climate
                 # OR duplicate the logic... duplicating is safer for strict instruction compliance now.
                 
                 if bin_interval:
                    bins = bin_history_data(states, start_time, end_time, bin_interval)
                    binned_values = []
                    for b in bins:
                        val = calculate_attribute_mean(b["states"], "current_temperature")
                        if val is not None:
                            binned_values.append({"start": b["start"], "value": round(val, 2)})
                    if binned_values:
                        c_data[entity_id] = binned_values
                 else:
                    val = calculate_attribute_mean(states, "current_temperature")
                    if val is not None:
                       c_data[entity_id] = round(val, 2)

        if c_data:
            summary["sensor_aggregates"]["radiator_temps_avg"] = c_data

    return summary
