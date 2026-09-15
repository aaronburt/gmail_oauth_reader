import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, OptionsFlowWithConfigEntry
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from .const import (
    CONF_POLL_INTERVAL,
    CONF_QUEUE_DWELL_TIME,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_QUEUE_DWELL_TIME,
    DOMAIN,
    GMAIL_PROFILE_URL,
    MAX_POLL_INTERVAL,
    MAX_QUEUE_DWELL_TIME,
    MIN_POLL_INTERVAL,
    MIN_QUEUE_DWELL_TIME,
    SCOPES,
)

_LOGGER = logging.getLogger(__name__)


class GmailOAuthFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler,
    domain=DOMAIN,
):
    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        return _LOGGER

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        return {
            "scope": " ".join(SCOPES),
            "access_type": "offline",
            "prompt": "consent",
        }

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> FlowResult:
        token = data.get("token", {}).get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        email_address = "Gmail Account"

        session = config_entry_oauth2_flow.async_get_clientsession(self.hass)
        try:
            async with session.get(GMAIL_PROFILE_URL, headers=headers) as resp:
                if resp.status == 200:
                    profile = await resp.json()
                    email_address = profile.get("emailAddress", "Gmail Account")
        except Exception:
            pass

        await self.async_set_unique_id(email_address)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=email_address,
            data=data,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowWithConfigEntry:
        return GmailOptionsFlowHandler(config_entry)


class GmailOptionsFlowHandler(OptionsFlowWithConfigEntry):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_POLL_INTERVAL,
                    default=self.options.get(
                        CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
                    ),
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_POLL_INTERVAL, max=MAX_POLL_INTERVAL),
                ),
                vol.Optional(
                    CONF_QUEUE_DWELL_TIME,
                    default=self.options.get(
                        CONF_QUEUE_DWELL_TIME, DEFAULT_QUEUE_DWELL_TIME
                    ),
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_QUEUE_DWELL_TIME, max=MAX_QUEUE_DWELL_TIME),
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
