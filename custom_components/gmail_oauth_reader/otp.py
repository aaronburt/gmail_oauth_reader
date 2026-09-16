import re
from typing import Final

MIN_OTP_LENGTH: Final = 4
MAX_OTP_LENGTH: Final = 8

COMMON_REJECTED_WORDS: Final = {
    "ACCESS",
    "ACCOUNT",
    "ACTION",
    "ACTIVE",
    "ALERT",
    "DEVICE",
    "DIGITS",
    "EXPIRE",
    "FAILED",
    "GOOGLE",
    "LOCKED",
    "LOGGED",
    "LOGINS",
    "MEMBER",
    "MOBILE",
    "NOTICE",
    "ONLINE",
    "PORTAL",
    "RECENT",
    "SECURE",
    "SIGNIN",
    "STATUS",
    "SYSTEM",
    "UPDATE",
    "VERIFY",
}

KEYWORD_PATTERN: Final = (
    r"(?:verification|security|confirmation|login|auth(?:entication)?|"
    r"one[- ]time|otp|2fa|passcode|pin)"
)

STEAM_GUARD_PATTERN: Final = re.compile(
    r"(?i)\bsteam\s+guard\s+code\s*[:\s]+([B-DF-HJ-NP-TV-Z0-9]{5})\b"
)

CODE_AFTER_KEYWORD_PATTERN: Final = re.compile(
    rf"(?i)\b{KEYWORD_PATTERN}(?:\s+(?:code|password|passcode))?\s*(?:is|:|\b)\s*[:#-]?\s*"
    rf"([0-9]{{3,4}}[\s-][0-9]{{3,4}}|[0-9]{{4,8}}|[A-Za-z0-9]{{5,8}})\b"
)

CODE_BEFORE_KEYWORD_PATTERN: Final = re.compile(
    rf"(?i)(?:\b[gG]-|\b)([0-9]{{3,4}}[\s-][0-9]{{3,4}}|[0-9]{{4,8}})\s+is\s+"
    rf"(?:your\s+)?(?:[\w-]+\s+)*{KEYWORD_PATTERN}\b"
)

CALENDAR_YEAR_PATTERN: Final = re.compile(r"202[0-9]|203[0-9]")
STEAM_GUARD_TOKEN_PATTERN: Final = re.compile(r"[B-DF-HJ-NP-TV-Z0-9]{5}")


def normalize_token(raw_token: str) -> str:
    return re.sub(r"[\s-]+", "", raw_token).strip()


def is_calendar_year(token: str) -> bool:
    return bool(CALENDAR_YEAR_PATTERN.fullmatch(token))


def is_valid_token(token: str) -> bool:
    normalized = normalize_token(token).upper()
    if not (MIN_OTP_LENGTH <= len(normalized) <= MAX_OTP_LENGTH):
        return False
    if normalized in COMMON_REJECTED_WORDS:
        return False
    if is_calendar_year(normalized):
        return False
    if normalized.isdigit():
        return True
    if STEAM_GUARD_TOKEN_PATTERN.fullmatch(normalized):
        return True
    if any(char.isdigit() for char in normalized) and normalized.isalnum():
        return True
    return False


def extract_from_text(text: str) -> str | None:
    if not text:
        return None

    steam_match = STEAM_GUARD_PATTERN.search(text)
    if steam_match:
        candidate = normalize_token(steam_match.group(1)).upper()
        if is_valid_token(candidate):
            return candidate

    before_matches = CODE_BEFORE_KEYWORD_PATTERN.finditer(text)
    for match in before_matches:
        candidate = normalize_token(match.group(1))
        if is_valid_token(candidate):
            return candidate

    after_matches = CODE_AFTER_KEYWORD_PATTERN.finditer(text)
    for match in after_matches:
        candidate = normalize_token(match.group(1))
        if is_valid_token(candidate):
            return candidate.upper() if not candidate.isdigit() else candidate

    return None


def extract_otp_code(subject: str, body_preview: str) -> str | None:
    if subject:
        subject_code = extract_from_text(subject)
        if subject_code:
            return subject_code

    if body_preview:
        return extract_from_text(body_preview)

    return None
