from datetime import timedelta
from unittest.mock import AsyncMock

from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gmail_oauth_reader.const import (
    DOMAIN,
    EVENT_GMAIL_NEW_EMAIL,
    EVENT_GMAIL_NEW_OTP,
    TRIGGER_TYPE_NEW_EMAIL,
    TRIGGER_TYPE_NEW_OTP,
)
from custom_components.gmail_oauth_reader.device_trigger import (
    async_attach_trigger,
    async_get_triggers,
)


async def test_async_get_triggers_matching_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    mock_config_entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, str(mock_config_entry.unique_id))},
    )

    triggers = await async_get_triggers(hass, device.id)
    assert len(triggers) == 2
    trigger_types = {trigger[CONF_TYPE] for trigger in triggers}
    assert trigger_types == {TRIGGER_TYPE_NEW_EMAIL, TRIGGER_TYPE_NEW_OTP}

    for trigger in triggers:
        assert trigger[CONF_PLATFORM] == "device"
        assert trigger[CONF_DOMAIN] == DOMAIN
        assert trigger[CONF_DEVICE_ID] == device.id


async def test_async_get_triggers_unknown_or_unrelated_device(
    hass: HomeAssistant,
) -> None:
    triggers = await async_get_triggers(hass, "non_existent_device")
    assert triggers == []

    other_entry = MockConfigEntry(domain="other_domain", entry_id="other_entry_id")
    other_entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    other_device = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={("other_domain", "other_id")},
    )
    other_triggers = await async_get_triggers(hass, other_device.id)
    assert other_triggers == []


async def test_async_attach_trigger_fires_for_matching_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    mock_config_entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, str(mock_config_entry.unique_id))},
    )

    action = AsyncMock()
    trigger_info = {"trigger_data": {}, "variables": {}}
    config = {
        CONF_PLATFORM: "device",
        CONF_DEVICE_ID: device.id,
        CONF_DOMAIN: DOMAIN,
        CONF_TYPE: TRIGGER_TYPE_NEW_EMAIL,
    }

    remove_trigger = await async_attach_trigger(hass, config, action, trigger_info)

    hass.bus.async_fire(
        EVENT_GMAIL_NEW_EMAIL,
        {"message_id": "123", "entry_id": mock_config_entry.entry_id},
    )
    await hass.async_block_till_done()
    assert action.called

    action.reset_mock()
    hass.bus.async_fire(
        EVENT_GMAIL_NEW_EMAIL,
        {"message_id": "124", "entry_id": "different_entry_id"},
    )
    await hass.async_block_till_done()
    assert not action.called

    remove_trigger()
