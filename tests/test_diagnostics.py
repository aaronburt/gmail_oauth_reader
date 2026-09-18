from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gmail_oauth_reader.const import DOMAIN
from custom_components.gmail_oauth_reader.coordinator import GmailDataUpdateCoordinator
from custom_components.gmail_oauth_reader.diagnostics import (
    async_get_config_entry_diagnostics,
)


async def test_diagnostics_redaction(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_oauth_session: MagicMock,
) -> None:
    mock_config_entry.add_to_hass(hass)
    coordinator = GmailDataUpdateCoordinator(
        hass=hass,
        entry=mock_config_entry,
        session=mock_oauth_session,
        update_interval=timedelta(seconds=60),
    )
    coordinator._unread_count = 5
    coordinator._last_polled = datetime(2026, 9, 18, 14, 30, tzinfo=timezone.utc)
    hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = coordinator

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    assert 'entry' in diagnostics
    assert 'coordinator' in diagnostics

    coord_diag = diagnostics['coordinator']
    assert coord_diag['unread_count'] == 5
    assert coord_diag['last_polled'] == '2026-09-18T14:30:00+00:00'
    assert coord_diag['queue_size'] == 0
    assert coord_diag['has_active_message'] is False

    entry_data = diagnostics['entry']['data']
    assert entry_data['token'] == '**REDACTED**'
