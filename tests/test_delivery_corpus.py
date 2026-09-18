from datetime import timedelta
from pathlib import Path
import re
from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gmail_oauth_reader.coordinator import (
    GmailDataUpdateCoordinator,
    decode_mime_header,
    extract_service_name,
    parse_email_date,
    parse_sender_components,
    sanitize_text,
)

REAL_EMAILS_DIR = Path.home() / "Desktop" / "Delivery" / "emails"


def test_helper_decode_mime_header() -> None:
    assert decode_mime_header('Simple Subject') == 'Simple Subject'
    assert decode_mime_header('') == ''
    encoded = '=?utf-8?B?WW91ciBPcmRlcg==?='
    assert decode_mime_header(encoded) == 'Your Order'


def test_helper_parse_sender_components() -> None:
    display, name, email_addr = parse_sender_components('Amazon Deliveries <auto-confirm@amazon.co.uk>')
    assert display == 'Amazon Deliveries'
    assert name == 'Amazon Deliveries'
    assert email_addr == 'auto-confirm@amazon.co.uk'

    display2, name2, email_addr2 = parse_sender_components('orders@iceland.co.uk')
    assert display2 == 'orders@iceland.co.uk'
    assert name2 == ''
    assert email_addr2 == 'orders@iceland.co.uk'

    assert parse_sender_components('') == ('', '', '')


def test_helper_extract_service_name_varieties() -> None:
    assert extract_service_name('DHL Express Alerts', 'no-reply@dhl.com') == 'DHL Express'
    assert extract_service_name('DPD UK Updates', 'service@dpd.co.uk') == 'DPD UK Updates'
    assert extract_service_name('Royal Mail Notifications', 'tracking@royalmail.co.uk') == 'Royal Mail'
    assert extract_service_name('', 'support@tesco.com') == 'Tesco'
    assert extract_service_name('', 'auto@asda.co.uk') == 'Asda'


def test_helper_parse_email_date() -> None:
    parsed = parse_email_date('Fri, 18 Sep 2026 12:00:00 +0000')
    assert '2026-09-18' in parsed
    raw_invalid = 'invalid-date-string'
    assert parse_email_date(raw_invalid) == raw_invalid


async def test_batch_corpus_real_emails(
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

    corpus_sample = [
        ('1807a5d893f8a197_dpd_delivered.html', 'DPD', 'service@dpd.co.uk'),
        ('18249e684e1c61ff_dhl_delivered.html', 'DHL', 'alerts@dhl.com'),
        ('18ab78711bca026e_yodel_delivered.html', 'Yodel', 'updates@yodel.co.uk'),
        ('18d5a6d96ea40a8e_asda_delivered.html', 'Asda', 'orders@asda.co.uk'),
        ('18a08f2f0e1d6730_littlewoods_dispatched.html', 'Littlewoods', 'delivery@littlewoods.com'),
        ('19ffa95666c8201b_ambrose_wilson_general_update.html', 'Ambrose Wilson', 'service@ambrosewilson.com'),
        ('19ff6ddbbe3e8760_well_pharmacy_dispatched.html', 'Well Pharmacy', 'prescriptions@well.co.uk'),
    ]

    for filename, brand, sender_addr in corpus_sample:
        path = REAL_EMAILS_DIR / filename
        assert path.exists()
        raw = path.read_text(encoding='utf-8', errors='ignore')
        clean = re.sub(r'<[^>]+>', ' ', raw)
        preview = sanitize_text(clean, 100)
        assert len(preview) > 0

        msg_id = await coordinator.async_simulate_email(
            sender=brand + ' <' + sender_addr + '>',
            subject=brand + ' update',
            body=preview,
        )
        assert msg_id.startswith('sim_')
        full = await coordinator.async_get_full_email(msg_id)
        assert full['sender_email'] == sender_addr

    coordinator.cancel_queue_task()


def test_decode_base64url_and_bytes() -> None:
    from custom_components.gmail_oauth_reader.coordinator import (
        decode_base64url,
        decode_base64url_bytes,
    )

    assert decode_base64url_bytes('') == b''
    assert decode_base64url('') == ''

    encoded = 'SGVsbG8gV29ybGQ'
    assert decode_base64url(encoded) == 'Hello World'
    assert decode_base64url_bytes(encoded) == b'Hello World'


def test_extract_mime_bodies_and_attachments() -> None:
    from custom_components.gmail_oauth_reader.coordinator import (
        extract_mime_bodies_and_attachments,
    )

    payload = {
        'mimeType': 'multipart/mixed',
        'parts': [
            {
                'mimeType': 'text/plain',
                'body': {'data': 'UGxhaW4gdGV4dA'},
            },
            {
                'mimeType': 'text/html',
                'body': {'data': 'PHA-SFRNTDwvcD4'},
            },
            {
                'mimeType': 'application/pdf',
                'filename': 'invoice.pdf',
                'body': {'size': 2048, 'attachmentId': 'att_123'},
            },
        ],
    }

    text, html_body, attachments = extract_mime_bodies_and_attachments(payload)
    assert text == 'Plain text'
    assert html_body == '<p>HTML</p>'
    assert len(attachments) == 1
    assert attachments[0]['filename'] == 'invoice.pdf'
    assert attachments[0]['size'] == 2048
    assert attachments[0]['attachment_id'] == 'att_123'