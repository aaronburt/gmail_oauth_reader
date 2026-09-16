from datetime import timedelta
from pathlib import Path

import aiohttp
from aiohttp import web
import voluptuous as vol

from homeassistant.components import webhook
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
    CONF_UPDATE_MODE,
    CONF_WEBHOOK_ID,
    DEFAULT_DOWNLOAD_DIR,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    MODE_PUBSUB_PUSH,
)
from .coordinator import GmailDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]

SERVICE_GET_EMAIL_CONTENT = "get_email_content"
SERVICE_MODIFY_EMAIL = "modify_email"
SERVICE_DOWNLOAD_ATTACHMENT = "download_attachment"

SCHEMA_GET_EMAIL_CONTENT = vol.Schema(
    {
        vol.Optional("message_id"): cv.string,
        vol.Optional("entry_id"): cv.string,
    }
)

SCHEMA_MODIFY_EMAIL = vol.Schema(
    {
        vol.Optional("message_id"): cv.string,
        vol.Optional("mark_as_read", default=False): cv.boolean,
        vol.Optional("archive", default=False): cv.boolean,
        vol.Optional("add_labels"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("remove_labels"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("entry_id"): cv.string,
    }
)

SCHEMA_DOWNLOAD_ATTACHMENT = vol.Schema(
    {
        vol.Required("message_id"): cv.string,
        vol.Required("attachment_id"): cv.string,
        vol.Required("filename"): cv.string,
        vol.Optional("path"): cv.string,
        vol.Optional("entry_id"): cv.string,
    }
)


def get_webhook_id(entry: ConfigEntry) -> str:
    return entry.options.get(CONF_WEBHOOK_ID) or f"{DOMAIN}_{entry.entry_id}"


def async_register_push_webhook(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: GmailDataUpdateCoordinator,
) -> None:
    webhook_id = get_webhook_id(entry)
    if webhook.async_is_registered(hass, webhook_id):
        return

    async def handle_push_webhook(
        hass: HomeAssistant, w_id: str, request: web.Request
    ) -> web.Response:
        await coordinator.async_handle_pubsub_notification()
        return web.Response(status=200, text="OK")

    webhook.async_register(
        hass, DOMAIN, f"Gmail Push ({entry.title})", webhook_id, handle_push_webhook
    )


def async_unregister_push_webhook(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    webhook_id = get_webhook_id(entry)
    if webhook.async_is_registered(hass, webhook_id):
        webhook.async_unregister(hass, webhook_id)


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

    await coordinator.async_apply_update_mode()
    if coordinator.update_mode == MODE_PUBSUB_PUSH:
        async_register_push_webhook(hass, entry, coordinator)

    def get_coordinator(entry_id: str | None) -> GmailDataUpdateCoordinator:
        if entry_id and entry_id in hass.data[DOMAIN]:
            return hass.data[DOMAIN][entry_id]
        if hass.data.get(DOMAIN):
            return next(iter(hass.data[DOMAIN].values()))
        raise HomeAssistantError("No Gmail integration configured")

    def get_message_id(
        active_coordinator: GmailDataUpdateCoordinator,
        message_id: str | None,
    ) -> str:
        if message_id:
            return message_id
        if active_coordinator.data is not None:
            return active_coordinator.data.message_id
        if active_coordinator.last_message is not None:
            return active_coordinator.last_message.message_id
        raise HomeAssistantError(
            "No message_id provided and no recent email is available"
        )

    async def handle_get_email_content(call: ServiceCall) -> ServiceResponse:
        active_coordinator = get_coordinator(call.data.get("entry_id"))
        target_message_id = get_message_id(
            active_coordinator, call.data.get("message_id")
        )
        return await active_coordinator.async_get_full_email(target_message_id)

    async def handle_modify_email(call: ServiceCall) -> ServiceResponse:
        active_coordinator = get_coordinator(call.data.get("entry_id"))
        target_message_id = get_message_id(
            active_coordinator, call.data.get("message_id")
        )
        add_labels = list(call.data.get("add_labels") or [])
        remove_labels = list(call.data.get("remove_labels") or [])
        if call.data.get("mark_as_read") and "UNREAD" not in remove_labels:
            remove_labels.append("UNREAD")
        if call.data.get("archive") and "INBOX" not in remove_labels:
            remove_labels.append("INBOX")
        return await active_coordinator.async_modify_email(
            target_message_id, add_labels, remove_labels
        )

    async def handle_download_attachment(call: ServiceCall) -> ServiceResponse:
        active_coordinator = get_coordinator(call.data.get("entry_id"))
        msg_id = call.data["message_id"]
        att_id = call.data["attachment_id"]
        filename = Path(call.data["filename"]).name
        target_path = Path(
            call.data.get("path") or hass.config.path(DEFAULT_DOWNLOAD_DIR),
            filename,
        )

        content = await active_coordinator.async_download_attachment(msg_id, att_id)

        def write_file() -> str:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(content)
            return str(target_path)

        resolved_path = await hass.async_add_executor_job(write_file)
        return {
            "path": resolved_path,
            "filename": filename,
            "size": len(content),
        }

    if not hass.services.has_service(DOMAIN, SERVICE_GET_EMAIL_CONTENT):
        hass.services.async_register(
            DOMAIN,
            SERVICE_GET_EMAIL_CONTENT,
            handle_get_email_content,
            schema=SCHEMA_GET_EMAIL_CONTENT,
            supports_response=SupportsResponse.ONLY,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_MODIFY_EMAIL):
        hass.services.async_register(
            DOMAIN,
            SERVICE_MODIFY_EMAIL,
            handle_modify_email,
            schema=SCHEMA_MODIFY_EMAIL,
            supports_response=SupportsResponse.ONLY,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_DOWNLOAD_ATTACHMENT):
        hass.services.async_register(
            DOMAIN,
            SERVICE_DOWNLOAD_ATTACHMENT,
            handle_download_attachment,
            schema=SCHEMA_DOWNLOAD_ATTACHMENT,
            supports_response=SupportsResponse.ONLY,
        )

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        async_unregister_push_webhook(hass, entry)
        coordinator: GmailDataUpdateCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator.cancel_queue_task()
        await coordinator.async_stop_realtime()
        if not hass.data[DOMAIN]:
            for service_name in (
                SERVICE_GET_EMAIL_CONTENT,
                SERVICE_MODIFY_EMAIL,
                SERVICE_DOWNLOAD_ATTACHMENT,
            ):
                if hass.services.has_service(DOMAIN, service_name):
                    hass.services.async_remove(DOMAIN, service_name)
    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    coordinator: GmailDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_apply_update_mode()
    if coordinator.update_mode == MODE_PUBSUB_PUSH:
        async_register_push_webhook(hass, entry, coordinator)
    else:
        async_unregister_push_webhook(hass, entry)
