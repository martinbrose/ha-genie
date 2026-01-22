"""Provides device triggers for HA Genie."""
import logging
import voluptuous as vol

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers import config_validation as cv
from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

TRIGGER_TYPE_REPORT_READY = "report_ready"

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required("type"): TRIGGER_TYPE_REPORT_READY,
    }
)

async def async_get_triggers(hass: HomeAssistant, device_id: str):
    """Return a list of triggers."""
    return [
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_id,
            "type": TRIGGER_TYPE_REPORT_READY,
        }
    ]

async def async_attach_trigger(
    hass: HomeAssistant,
    config: dict,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
):
    """Attach a trigger."""
    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: f"{DOMAIN}_report_ready",
        }
    )
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )
