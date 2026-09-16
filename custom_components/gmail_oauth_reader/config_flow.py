import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry, OptionsFlowWithConfigEntry
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_EXTRACT_OTP,
    CONF_OTP_EXPIRY_MINUTES,
    CONF_POLL_INTERVAL,
    CONF_PUBSUB_PROJECT_ID,
    CONF_PUBSUB_SUBSCRIPTION,
    CONF_PUBSUB_TOPIC,
    CONF_QUERY,
    CONF_QUEUE_DWELL_TIME,
    CONF_SAFETY_POLL_INTERVAL,
    CONF_UPDATE_MODE,
    CONF_WEBHOOK_ID,
    DEFAULT_EXTRACT_OTP,
    DEFAULT_OTP_EXPIRY_MINUTES,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_QUERY,
    DEFAULT_QUEUE_DWELL_TIME,
    DEFAULT_SAFETY_POLL_INTERVAL,
    DEFAULT_UPDATE_MODE,
    DOMAIN,
    GMAIL_PROFILE_URL,
    MAX_OTP_EXPIRY_MINUTES,
    MAX_POLL_INTERVAL,
    MAX_QUEUE_DWELL_TIME,
    MAX_SAFETY_POLL_INTERVAL,
    MIN_OTP_EXPIRY_MINUTES,
    MIN_POLL_INTERVAL,
    MIN_QUEUE_DWELL_TIME,
    MIN_SAFETY_POLL_INTERVAL,
    MODE_POLLING,
    MODE_PUBSUB_PULL,
    MODE_PUBSUB_PUSH,
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
        webhook_id = (
            self.options.get(CONF_WEBHOOK_ID)
            or f"{DOMAIN}_{self.config_entry.entry_id}"
        )

        if user_input is not None:
            user_input[CONF_WEBHOOK_ID] = webhook_id
            return self.async_create_entry(title="", data=user_input)

        webhook_url = webhook.async_generate_url(self.hass, webhook_id)
        current_mode = self.options.get(CONF_UPDATE_MODE, DEFAULT_UPDATE_MODE)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_UPDATE_MODE,
                    default=current_mode,
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(
                                value=MODE_POLLING,
                                label="Polling (Traditional)",
                            ),
                            SelectOptionDict(
                                value=MODE_PUBSUB_PULL,
                                label="Google Cloud Pub/Sub (Pull)",
                            ),
                            SelectOptionDict(
                                value=MODE_PUBSUB_PUSH,
                                label="Google Cloud Pub/Sub (Push / Webhook)",
                            ),
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key="update_mode",
                    )
                ),
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
                    CONF_PUBSUB_PROJECT_ID,
                    default=self.options.get(CONF_PUBSUB_PROJECT_ID, ""),
                ): str,
                vol.Optional(
                    CONF_PUBSUB_TOPIC,
                    default=self.options.get(CONF_PUBSUB_TOPIC, ""),
                ): str,
                vol.Optional(
                    CONF_PUBSUB_SUBSCRIPTION,
                    default=self.options.get(CONF_PUBSUB_SUBSCRIPTION, ""),
                ): str,
                vol.Optional(
                    CONF_SAFETY_POLL_INTERVAL,
                    default=self.options.get(
                        CONF_SAFETY_POLL_INTERVAL, DEFAULT_SAFETY_POLL_INTERVAL
                    ),
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(
                        min=MIN_SAFETY_POLL_INTERVAL,
                        max=MAX_SAFETY_POLL_INTERVAL,
                    ),
                ),
                vol.Optional(
                    CONF_QUERY,
                    default=self.options.get(CONF_QUERY, DEFAULT_QUERY),
                ): str,
                vol.Optional(
                    CONF_QUEUE_DWELL_TIME,
                    default=self.options.get(
                        CONF_QUEUE_DWELL_TIME, DEFAULT_QUEUE_DWELL_TIME
                    ),
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(
                        min=MIN_QUEUE_DWELL_TIME, max=MAX_QUEUE_DWELL_TIME
                    ),
                ),
                vol.Optional(
                    CONF_EXTRACT_OTP,
                    default=self.options.get(
                        CONF_EXTRACT_OTP, DEFAULT_EXTRACT_OTP
                    ),
                ): bool,
                vol.Optional(
                    CONF_OTP_EXPIRY_MINUTES,
                    default=self.options.get(
                        CONF_OTP_EXPIRY_MINUTES, DEFAULT_OTP_EXPIRY_MINUTES
                    ),
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(
                        min=MIN_OTP_EXPIRY_MINUTES,
                        max=MAX_OTP_EXPIRY_MINUTES,
                    ),
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            description_placeholders={"webhook_url": webhook_url},
        )
