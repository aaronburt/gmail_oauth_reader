from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gmail_oauth_reader.const import DOMAIN, STATE_IDLE
from custom_components.gmail_oauth_reader.coordinator import (
    GmailDataUpdateCoordinator,
    GmailMessage,
)
from custom_components.gmail_oauth_reader.sensor import (
    GmailLastPolledSensor,
    GmailLatestEmailSensor,
    GmailLatestOTPSensor,
    GmailQueueSizeSensor,
    GmailUnreadCountSensor,
    async_setup_entry,
)


async def test_sensor_setup_entry(
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
    hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = coordinator

    added_entities = []
    await async_setup_entry(hass, mock_config_entry, added_entities.extend)
    assert len(added_entities) == 5


async def test_latest_email_sensor_states_and_attributes(
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
    sensor = GmailLatestEmailSensor(coordinator, mock_config_entry)

    assert sensor.native_value == STATE_IDLE
    assert sensor.extra_state_attributes['messages'] == []
    assert sensor.extra_state_attributes['queue_size'] == 0
    assert sensor.extra_state_attributes['unread_count'] == 0

    test_msg = GmailMessage(
        message_id='msg_101',
        sender='Acme <support@acme.com>',
        sender_name='Acme',
        sender_email='support@acme.com',
        subject='Order #1234',
        body_preview='Your order has shipped',
        received_time='2026-09-18T10:00:00Z',
        otp_code=None,
    )
    coordinator.data = test_msg
    assert sensor.native_value == 'msg_101'
    attrs = sensor.extra_state_attributes
    assert attrs['subject'] == 'Order #1234'
    assert attrs['sender'] == 'Acme <support@acme.com>'
    assert attrs['sender_name'] == 'Acme'
    assert attrs['sender_email'] == 'support@acme.com'
    assert attrs['body_preview'] == 'Your order has shipped'


async def test_latest_otp_sensor_states_and_attributes(
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
    sensor = GmailLatestOTPSensor(coordinator, mock_config_entry)

    assert sensor.native_value == STATE_IDLE
    assert sensor.extra_state_attributes == {}

    otp_msg = GmailMessage(
        message_id='msg_202',
        sender='GitHub <support@github.com>',
        sender_name='GitHub',
        sender_email='support@github.com',
        subject='GitHub Security Code',
        body_preview='Code is 849201',
        received_time='2026-09-18T10:05:00Z',
        otp_code='849201',
    )
    coordinator._latest_otp = otp_msg
    coordinator._otp_received_at = datetime.now(timezone.utc)

    assert sensor.native_value == '849201'
    attrs = sensor.extra_state_attributes
    assert attrs['service_name'] == 'GitHub'
    assert attrs['subject'] == 'GitHub Security Code'
    assert attrs['message_id'] == 'msg_202'
    assert 'expires_at' in attrs


async def test_unread_count_queue_size_and_last_polled(
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

    unread_sensor = GmailUnreadCountSensor(coordinator, mock_config_entry)
    queue_sensor = GmailQueueSizeSensor(coordinator, mock_config_entry)
    polled_sensor = GmailLastPolledSensor(coordinator, mock_config_entry)

    assert unread_sensor.native_value == 0
    assert queue_sensor.native_value == 0
    assert polled_sensor.native_value is None

    coordinator._unread_count = 7
    coordinator._last_polled = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)

    assert unread_sensor.native_value == 7
    assert polled_sensor.native_value == datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
