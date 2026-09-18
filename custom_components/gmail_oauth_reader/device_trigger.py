from __future__ import annotations

from typing import Any
import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    EVENT_GMAIL_NEW_EMAIL,
    EVENT_GMAIL_NEW_OTP,
    TRIGGER_TYPE_NEW_EMAIL,
    TRIGGER_TYPE_NEW_OTP,
)

TRIGGER_TYPES = {TRIGGER_TYPE_NEW_EMAIL, TRIGGER_TYPE_NEW_OTP}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    if device is None:
        return []

    is_matching_device = any(
        identifier[0] == DOMAIN for identifier in device.identifiers
    )
    if not is_matching_device:
        return []

    return [
        {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: trigger_type,
        }
        for trigger_type in sorted(TRIGGER_TYPES)
    ]


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    trigger_type = config[CONF_TYPE]
    event_type = (
        EVENT_GMAIL_NEW_OTP
        if trigger_type == TRIGGER_TYPE_NEW_OTP
        else EVENT_GMAIL_NEW_EMAIL
    )

    device_registry = dr.async_get(hass)
    device = device_registry.async_get(config[CONF_DEVICE_ID])

    event_data: dict[str, Any] = {}
    if device is not None and device.config_entries:
        entry_id = next(iter(device.config_entries))
        event_data["entry_id"] = entry_id

    event_config_dict: dict[str, Any] = {
        event_trigger.CONF_PLATFORM: "event",
        event_trigger.CONF_EVENT_TYPE: event_type,
    }
    if event_data:
        event_config_dict[event_trigger.CONF_EVENT_DATA] = event_data

    event_config = event_trigger.TRIGGER_SCHEMA(event_config_dict)
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )
