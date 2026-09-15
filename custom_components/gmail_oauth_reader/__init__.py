from datetime import timedelta

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv

from .const import (
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)
from .coordinator import GmailDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]
SERVICE_GET_EMAIL_CONTENT = "get_email_content"
SCHEMA_GET_EMAIL_CONTENT = vol.Schema(
    {
        vol.Optional("message_id"): cv.string,
        vol.Optional("entry_id"): cv.string,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(
        hass, entry, implementation
    )
    try:
        await session.async_ensure_token_valid()
    except Exception as err:
        raise ConfigEntryAuthFailed(f"OAuth token is invalid: {err}") from err

    poll_interval = entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
    coordinator = GmailDataUpdateCoordinator(
        hass=hass,
        entry=entry,
        session=session,
        update_interval=timedelta(seconds=poll_interval),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    async def handle_get_email_content(call: ServiceCall) -> ServiceResponse:
        entry_id = call.data.get("entry_id")
        if entry_id and entry_id in hass.data[DOMAIN]:
            active_coordinator = hass.data[DOMAIN][entry_id]
        elif hass.data.get(DOMAIN):
            active_coordinator = next(iter(hass.data[DOMAIN].values()))
        else:
            raise HomeAssistantError("No Gmail integration configured")

        target_message_id = call.data.get("message_id")
        if not target_message_id:
            if active_coordinator.data is not None:
                target_message_id = active_coordinator.data.message_id
            elif active_coordinator.last_message is not None:
                target_message_id = active_coordinator.last_message.message_id
            else:
                raise HomeAssistantError(
                    "No message_id provided and no recent email is available"
                )

        return await active_coordinator.async_get_full_email(target_message_id)

    if not hass.services.has_service(DOMAIN, SERVICE_GET_EMAIL_CONTENT):
        hass.services.async_register(
            DOMAIN,
            SERVICE_GET_EMAIL_CONTENT,
            handle_get_email_content,
            schema=SCHEMA_GET_EMAIL_CONTENT,
            supports_response=SupportsResponse.ONLY,
        )

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: GmailDataUpdateCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator.cancel_queue_task()
        if not hass.data[DOMAIN] and hass.services.has_service(
            DOMAIN, SERVICE_GET_EMAIL_CONTENT
        ):
            hass.services.async_remove(DOMAIN, SERVICE_GET_EMAIL_CONTENT)
    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    coordinator: GmailDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    new_interval = entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
    coordinator.update_interval = timedelta(seconds=new_interval)
