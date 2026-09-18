from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gmail_oauth_reader.const import DOMAIN
from custom_components.gmail_oauth_reader.repairs import (
    AuthExpiredRepairFlow,
    async_create_fix_flow,
    async_create_issue,
    async_delete_issue,
    get_issue_id,
)


async def test_create_and_delete_repair_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    mock_config_entry.add_to_hass(hass)
    issue_id = get_issue_id(mock_config_entry.entry_id)

    async_create_issue(hass, mock_config_entry)

    issue_reg = ir.async_get(hass)
    issue = issue_reg.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.domain == DOMAIN
    assert issue.issue_id == issue_id
    assert issue.translation_key == "auth_failed"
    assert issue.severity == ir.IssueSeverity.ERROR

    async_delete_issue(hass, mock_config_entry.entry_id)
    assert issue_reg.async_get_issue(DOMAIN, issue_id) is None


async def test_auth_expired_repair_flow_confirmation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    mock_config_entry.add_to_hass(hass)
    flow = AuthExpiredRepairFlow(mock_config_entry)
    flow.hass = hass

    init_result = await flow.async_step_init()
    assert init_result["type"] == FlowResultType.FORM
    assert init_result["step_id"] == "confirm"

    mock_config_entry.async_start_reauth = AsyncMock()

    confirm_result = await flow.async_step_confirm(user_input={})
    assert confirm_result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert mock_config_entry.async_start_reauth.called


async def test_async_create_fix_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    mock_config_entry.add_to_hass(hass)
    issue_id = get_issue_id(mock_config_entry.entry_id)

    flow = await async_create_fix_flow(
        hass,
        issue_id,
        {"entry_id": mock_config_entry.entry_id},
    )
    assert isinstance(flow, AuthExpiredRepairFlow)
    assert flow.entry.entry_id == mock_config_entry.entry_id
