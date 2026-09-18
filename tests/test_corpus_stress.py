from pathlib import Path
import re
import pytest

from custom_components.gmail_oauth_reader.otp import extract_otp_code
from custom_components.gmail_oauth_reader.coordinator import (
    extract_service_name,
    sanitize_text,
)

CORPUS_DIR = Path.home() / "Desktop" / "Delivery" / "emails"


def test_full_corpus_parsing_and_otp_extraction():
    if not CORPUS_DIR.exists():
        pytest.skip("Delivery emails corpus directory not found")

    email_files = list(CORPUS_DIR.glob("*.html"))
    assert len(email_files) > 0, "Expected delivery email files in corpus"

    parsed_count = 0
    otps_found = 0
    couriers_detected = set()

    for file_path in email_files[:100]:
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        parsed_count += 1
        plain_text = sanitize_text(content)
        assert isinstance(plain_text, str)

        title_match = re.search(r"<title[^>]*>(.*?)</title>", content, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else file_path.stem

        service = extract_service_name(title, sender_email="")
        if service != "Unknown":
            couriers_detected.add(service)

        otp_code = extract_otp_code(title, plain_text)
        if otp_code:
            otps_found += 1
            assert len(otp_code) in (4, 5, 6, 7, 8)
            assert not otp_code.startswith("202")

    assert parsed_count >= 50
    assert len(couriers_detected) > 0
