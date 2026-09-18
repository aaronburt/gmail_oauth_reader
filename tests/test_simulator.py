from datetime import timedelta
from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gmail_oauth_reader.button import GmailSimulateTestEmailButton
from custom_components.gmail_oauth_reader.const import SIMULATED_MESSAGE_PREFIX
from custom_components.gmail_oauth_reader.coordinator import GmailDataUpdateCoordinator


async def test_async_simulate_email_default_generation(
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

    message_id = await coordinator.async_simulate_email()
    assert message_id.startswith(SIMULATED_MESSAGE_PREFIX)
    assert message_id in coordinator._simulated_messages

    cached = coordinator._simulated_messages[message_id]
    assert cached["sender"] == "Home Assistant Simulator"
    assert cached["sender_email"] == "simulator@homeassistant.local"
    assert cached["otp_code"] is not None
    assert len(cached["otp_code"]) == 6
    assert cached["otp_code"].isdigit()
    coordinator.cancel_queue_task()


async def test_async_simulate_email_custom_fields(
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

    message_id = await coordinator.async_simulate_email(
        sender="Acme Corp <security@acme.corp>",
        subject="Your custom login code",
        body="Verification code: 123456",
        otp_code="123456",
    )

    cached = coordinator._simulated_messages[message_id]
    assert cached["sender_name"] == "Acme Corp"
    assert cached["sender_email"] == "security@acme.corp"
    assert cached["subject"] == "Your custom login code"
    assert cached["otp_code"] == "123456"
    assert "Verification code: 123456" in cached["text_body"]
    coordinator.cancel_queue_task()


async def test_mock_secondary_action_interceptor(
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

    sim_id = "sim_fixture_abc"
    full_email = await coordinator.async_get_full_email(sim_id)
    assert full_email["message_id"] == sim_id
    assert "SIMULATED" in full_email["labels"]

    modify_res = await coordinator.async_modify_email(sim_id, add_labels=["STARRED"])
    assert modify_res["message_id"] == sim_id
    assert modify_res["labels"] == ["SIMULATED"]

    assert not mock_oauth_session.async_request.called


async def test_simulate_test_email_button(
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

    button = GmailSimulateTestEmailButton(coordinator, mock_config_entry)
    assert button.unique_id == f"{mock_config_entry.unique_id}_simulate_test_email"
    assert button.icon == "mdi:email-fast-outline"

    await button.async_press()
    assert len(coordinator._simulated_messages) == 1
    coordinator.cancel_queue_task()


async def test_poll_now_button_and_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_oauth_session: MagicMock,
) -> None:
    from custom_components.gmail_oauth_reader.button import (
        GmailPollNowButton,
        async_setup_entry as async_setup_button_entry,
    )
    from custom_components.gmail_oauth_reader.const import DOMAIN

    mock_config_entry.add_to_hass(hass)
    coordinator = GmailDataUpdateCoordinator(
        hass=hass,
        entry=mock_config_entry,
        session=mock_oauth_session,
        update_interval=timedelta(seconds=60),
    )
    hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = coordinator

    poll_button = GmailPollNowButton(coordinator, mock_config_entry)
    assert poll_button.unique_id == f"{mock_config_entry.unique_id}_poll_now"

    added_buttons = []
    await async_setup_button_entry(hass, mock_config_entry, added_buttons.extend)
    assert len(added_buttons) == 2
    coordinator.cancel_queue_task()


async def test_real_delivery_emails_parsing_and_simulation(
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

    from pathlib import Path
    import re
    from custom_components.gmail_oauth_reader.coordinator import sanitize_text, extract_service_name

    real_dir = Path(r"C:\Users\Aaron\Desktop\Delivery\emails")
    test_cases = [
        ("1a0a9da6b2839561_iceland_out_for_delivery.html", "Iceland", "orders@iceland.co.uk"),
        ("1a0a992c473cb620_evri_delivered.html", "Evri", "tracking@evri.com"),
        ("1a0ad52c3a923f3f_amazon_uk_dispatched.html", "Amazon", "auto-confirm@amazon.co.uk"),
        ("1711a7e80487dbf7_tesco_general_update.html", "Tesco", "online@tesco.co.uk"),
        ("1901a7297fdc3e8c_ebay_dispatched.html", "eBay", "ebay@ebay.co.uk"),
    ]

    for filename, carrier, email_addr in test_cases:
        filepath = real_dir / filename
        assert filepath.exists()
        raw_html = filepath.read_text(encoding="utf-8", errors="ignore")
        assert len(raw_html) > 0

        clean_text = re.sub(r"<[^>]+>", " ", raw_html)
        preview = sanitize_text(clean_text, 150)
        assert len(preview) > 0
        assert "<" not in preview and ">" not in preview

        service = extract_service_name(carrier, email_addr)
        assert len(service) > 0

        msg_id = await coordinator.async_simulate_email(
            sender=f"{carrier} <{email_addr}>",
            subject=f"{carrier} package delivery notice",
            body=preview,
        )
        assert msg_id.startswith(SIMULATED_MESSAGE_PREFIX)
        cached = coordinator._simulated_messages[msg_id]
        assert cached["sender_email"] == email_addr
        assert cached["sender_name"] == carrier

        full = await coordinator.async_get_full_email(msg_id)
        assert full["message_id"] == msg_id
        assert full["text_body"] == preview

    coordinator.cancel_queue_task()


async def test_real_delivery_email_otp_extraction(
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

    from pathlib import Path
    import re
    from custom_components.gmail_oauth_reader.coordinator import sanitize_text

    iceland_path = Path(r"C:\Users\Aaron\Desktop\Delivery\emails\19770596776c5d52_iceland_general_update.html")
    assert iceland_path.exists()
    raw_html = iceland_path.read_text(encoding="utf-8", errors="ignore")
    clean_text = re.sub(r"<[^>]+>", " ", raw_html)
    preview = sanitize_text(clean_text, 200)

    msg_id = await coordinator.async_simulate_email(
        sender="Iceland Groceries <deliveries@iceland.co.uk>",
        subject="Your delivery verification code is 502996",
        body=preview,
        otp_code="502996",
    )
    assert msg_id.startswith(SIMULATED_MESSAGE_PREFIX)
    cached = coordinator._simulated_messages[msg_id]
    assert cached["otp_code"] == "502996"
    assert cached["sender_email"] == "deliveries@iceland.co.uk"
    assert cached["sender_name"] == "Iceland Groceries"

    full = await coordinator.async_get_full_email(msg_id)
    assert full["message_id"] == msg_id
    assert full["otp_code"] == "502996"
    assert "502996" in full["subject"]

    coordinator.cancel_queue_task()
