import asyncio
from datetime import timedelta
from unittest.mock import MagicMock
import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gmail_oauth_reader.const import DOMAIN
from custom_components.gmail_oauth_reader.coordinator import GmailDataUpdateCoordinator

@pytest.mark.asyncio
async def test_burst_queue_and_otp_priority(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id='email@aaronburt.co.uk',
        data={'auth_implementation': 'google'},
        options={'dwell_time': 2, 'scan_interval': 300},
    )
    entry.add_to_hass(hass)

    mock_session = MagicMock()
    coordinator = GmailDataUpdateCoordinator(hass, entry, mock_session, timedelta(seconds=300))
    coordinator._service = MagicMock()

    for i in range(10):
        await coordinator.async_simulate_email(
            sender=f'Retailer <promo{i}@retail.co.uk>',
            subject=f'Special Offer #{i}',
            body=f'Save 20% today #{i}',
            otp_code='',
        )

    assert coordinator.queue_size == 9
    assert coordinator.last_message is not None
    assert coordinator.last_message.subject == 'Special Offer #0'

    iceland_id = await coordinator.async_simulate_email(
        sender='Iceland <pin@iceland.co.uk>',
        subject='Your Delivery PIN is 502996',
        body='Please give 502996 to your Iceland driver.',
        otp_code='502996',
    )

    assert coordinator.queue_size == 10
    assert coordinator._queue[0].message_id == iceland_id
    assert coordinator._queue[0].otp_code == '502996'
    assert coordinator._queue[0].subject == 'Your Delivery PIN is 502996'

    assert coordinator._queue[1].subject == 'Special Offer #1'

    coordinator.cancel_queue_task()
