from custom_components.gmail_oauth_reader.otp import (
    extract_from_text,
    extract_otp_code,
    is_calendar_year,
    is_valid_token,
    normalize_token,
)


def test_normalize_token() -> None:
    assert normalize_token(' 123-456 ') == '123456'
    assert normalize_token('12 34 56') == '123456'
    assert normalize_token('ABCD-EF') == 'ABCDEF'


def test_is_calendar_year() -> None:
    assert is_calendar_year('2024') is True
    assert is_calendar_year('2026') is True
    assert is_calendar_year('2031') is True
    assert is_calendar_year('1999') is False
    assert is_calendar_year('123456') is False
    assert is_calendar_year('2040') is False


def test_is_valid_token() -> None:
    assert is_valid_token('123') is False
    assert is_valid_token('123456789') is False
    assert is_valid_token('ACCESS') is False
    assert is_valid_token('VERIFY') is False
    assert is_valid_token('GOOGLE') is False
    assert is_valid_token('2025') is False
    assert is_valid_token('1234') is True
    assert is_valid_token('123456') is True
    assert is_valid_token('98765432') is True
    assert is_valid_token('K9M2P') is True
    assert is_valid_token('AB12CD') is True
    assert is_valid_token('pureletters') is False


def test_extract_from_text_steam_guard() -> None:
    text = 'Your Steam Guard code: K9M2P. Enter this code to sign in.'
    assert extract_from_text(text) == 'K9M2P'


def test_extract_from_text_code_before_keyword() -> None:
    text1 = '482910 is your verification code.'
    assert extract_from_text(text1) == '482910'

    text2 = 'G-984123 is your Google security code.'
    assert extract_from_text(text2) == '984123'

    text3 = '123-456 is your confirmation code.'
    assert extract_from_text(text3) == '123456'


def test_extract_from_text_code_after_keyword() -> None:
    text1 = 'Your verification code is 849201.'
    assert extract_from_text(text1) == '849201'

    text2 = 'Security passcode: 771234'
    assert extract_from_text(text2) == '771234'

    text3 = 'Use this login pin: 9941'
    assert extract_from_text(text3) == '9941'

    text4 = 'Your one-time passcode is: 654-321'
    assert extract_from_text(text4) == '654321'


def test_extract_from_text_empty_and_no_match() -> None:
    assert extract_from_text('') is None
    assert extract_from_text('Hello world, your package has been delivered.') is None
    assert extract_from_text('Your verification code is ACCESS') is None


def test_extract_otp_code_priority() -> None:
    subject = 'Your verification code is 112233'
    body = 'Another code is 445566'
    assert extract_otp_code(subject, body) == '112233'


def test_extract_otp_code_body_fallback() -> None:
    subject = 'Security Alert'
    body = 'Your security passcode is 998877'
    assert extract_otp_code(subject, body) == '998877'


def test_extract_otp_code_none() -> None:
    assert extract_otp_code('', '') is None
    assert extract_otp_code('Invoice', 'Here is your invoice for ') is None
