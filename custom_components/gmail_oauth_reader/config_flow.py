import asyncio
from collections.abc import Mapping
import logging
from typing import Any, cast

import voluptuous as vol

from homeassistant.components import webhook
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    OptionsFlowWithConfigEntry,
)
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
    CONF_ENABLE_WRITE,
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
    DEFAULT_ENABLE_WRITE,
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
    SCOPE_GMAIL_SEND,
    SCOPES,
)

_LOGGER = logging.getLogger(__name__)


class GmailOAuthFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler,
    domain=DOMAIN,
):
    DOMAIN = DOMAIN

    def __init__(self) -> None:
        super().__init__()
        self._enable_write: bool = DEFAULT_ENABLE_WRITE

    @property
    def logger(self) -> logging.Logger:
        return _LOGGER

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        scopes = list(SCOPES)
        if self._enable_write:
            scopes.append(SCOPE_GMAIL_SEND)
        return {
            "scope": " ".join(scopes),
            "access_type": "offline",
            "prompt": "consent",
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            self._enable_write = user_input.get(
                CONF_ENABLE_WRITE, DEFAULT_ENABLE_WRITE
            )
            return await self.async_step_pick_implementation()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ENABLE_WRITE,
                        default=DEFAULT_ENABLE_WRITE,
                    ): bool,
                }
            ),
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> FlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        reauth_entry = self._get_reauth_entry()
        current_write = reauth_entry.options.get(
            CONF_ENABLE_WRITE,
            reauth_entry.data.get(CONF_ENABLE_WRITE, DEFAULT_ENABLE_WRITE),
        )
        if user_input is not None:
            self._enable_write = user_input.get(
                CONF_ENABLE_WRITE, current_write
            )
            return await self.async_step_pick_implementation()

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ENABLE_WRITE,
                        default=current_write,
                    ): bool,
                }
            ),
        )

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> FlowResult:
        token = data.get("token", {}).get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        email_address = "Gmail Account"

        session = config_entry_oauth2_flow.async_get_clientsession(self.hass)
        try:
            async with asyncio.timeout(10):
                async with session.get(GMAIL_PROFILE_URL, headers=headers) as resp:
                    if resp.status == 200:
                        profile = await resp.json()
                        email_address = profile.get("emailAddress", "Gmail Account")
        except Exception:
            pass

        await self.async_set_unique_id(email_address)

        if self.source == SOURCE_REAUTH:
            reauth_entry = self._get_reauth_entry()
            self._abort_if_unique_id_mismatch(
                reason="wrong_account",
                description_placeholders={"email": cast(str, reauth_entry.unique_id)},
            )
            data[CONF_ENABLE_WRITE] = self._enable_write
            new_options = dict(reauth_entry.options)
            new_options[CONF_ENABLE_WRITE] = self._enable_write
            return self.async_update_reload_and_abort(
                reauth_entry, data=data, options=new_options
            )

        self._abort_if_unique_id_configured()

        data[CONF_ENABLE_WRITE] = self._enable_write
        return self.async_create_entry(
            title=email_address,
            data=data,
            options={CONF_ENABLE_WRITE: self._enable_write},
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
        previously_enabled = self.options.get(
            CONF_ENABLE_WRITE,
            self.config_entry.data.get(CONF_ENABLE_WRITE, DEFAULT_ENABLE_WRITE),
        )

        if user_input is not None:
            user_input[CONF_WEBHOOK_ID] = webhook_id
            new_enabled = user_input.get(CONF_ENABLE_WRITE, False)
            if new_enabled and not previously_enabled:
                self.config_entry.async_start_reauth(self.hass)
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
                vol.Optional(
                    CONF_ENABLE_WRITE,
                    default=previously_enabled,
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            description_placeholders={"webhook_url": webhook_url},
        )
