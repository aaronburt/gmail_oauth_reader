from __future__ import annotations

from typing import Any
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN


class AuthExpiredRepairFlow(RepairsFlow):
    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__()
        self.entry = entry

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        return await self.async_step_confirm(user_input)

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        if user_input is not None:
            self.hass.async_create_task(self.entry.async_start_reauth(self.hass))
            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={"account": self.entry.title},
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, Any] | None,
) -> RepairsFlow:
    entry_id = str(data.get("entry_id")) if data else ""
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None:
        raise data_entry_flow.UnknownStep
    return AuthExpiredRepairFlow(entry)


def get_issue_id(entry_id: str) -> str:
    return f"auth_failed_{entry_id}"


@callback
def async_create_issue(hass: HomeAssistant, entry: ConfigEntry) -> None:
    ir.async_create_issue(
        hass=hass,
        domain=DOMAIN,
        issue_id=get_issue_id(entry.entry_id),
        is_fixable=True,
        is_persistent=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="auth_failed",
        translation_placeholders={"account": entry.title},
        data={"entry_id": entry.entry_id},
    )


@callback
def async_delete_issue(hass: HomeAssistant, entry_id: str) -> None:
    ir.async_delete_issue(
        hass=hass,
        domain=DOMAIN,
        issue_id=get_issue_id(entry_id),
    )
