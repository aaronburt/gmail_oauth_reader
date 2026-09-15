import asyncio
import base64
from collections import OrderedDict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import email.header
import email.utils
import html
import logging
import re
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_QUERY,
    CONF_QUEUE_DWELL_TIME,
    DEFAULT_QUERY,
    DEFAULT_QUEUE_DWELL_TIME,
    DOMAIN,
    GMAIL_MESSAGES_URL,
    MAX_BODY_PREVIEW_LENGTH,
    MAX_RECENT_EMAILS,
    MAX_SEEN_CACHE_SIZE,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class GmailMessage:
    message_id: str
    sender: str
    sender_name: str
    sender_email: str
    subject: str
    body_preview: str
    received_time: str


def decode_mime_header(header_value: str) -> str:
    if not header_value:
        return ""
    try:
        decoded_parts = email.header.decode_header(header_value)
        return str(email.header.make_header(decoded_parts))
    except Exception:
        return header_value


def parse_sender_components(raw_sender: str) -> tuple[str, str, str]:
    if not raw_sender:
        return "", "", ""
    name, address = email.utils.parseaddr(decode_mime_header(raw_sender))
    clean_name = name.strip("\"' ")
    clean_address = address.strip()
    return clean_name or clean_address, clean_name, clean_address


def sanitize_text(text: str, max_length: int = MAX_BODY_PREVIEW_LENGTH) -> str:
    if not text:
        return ""
    without_tags = re.sub(r"<[^>]+>", " ", text)
    unescaped = html.unescape(without_tags)
    without_urls = re.sub(r"https?://\S+|www\.\S+", "", unescaped)
    without_noise = re.sub(r"[-=_*~]{2,}", " ", without_urls)
    normalized = re.sub(r"\s+", " ", without_noise).strip()
    if len(normalized) > max_length:
        return normalized[:max_length].rstrip() + "..."
    return normalized


def parse_email_date(raw_date: str) -> str:
    if not raw_date:
        return datetime.now(timezone.utc).isoformat()
    try:
        return email.utils.parsedate_to_datetime(raw_date).isoformat()
    except Exception:
        return raw_date


def decode_base64url(data_str: str) -> str:
    if not data_str:
        return ""
    padding = 4 - (len(data_str) % 4)
    if padding and padding < 4:
        data_str += "=" * padding
    try:
        raw_bytes = base64.urlsafe_b64decode(data_str.encode("ascii"))
        return raw_bytes.decode("utf-8", errors="replace")
    except Exception:
        return ""


def extract_mime_bodies_and_attachments(
    payload: dict[str, Any],
) -> tuple[str, str, list[dict[str, Any]]]:
    text_parts: list[str] = []
    html_parts: list[str] = []
    attachments: list[dict[str, Any]] = []

    def walk(part: dict[str, Any]) -> None:
        mime_type = part.get("mimeType", "").lower()
        filename = part.get("filename", "")
        body = part.get("body", {})
        data = body.get("data")
        attachment_id = body.get("attachmentId")

        if filename or attachment_id:
            attachments.append(
                {
                    "filename": filename,
                    "mime_type": mime_type,
                    "size": body.get("size", 0),
                    "attachment_id": attachment_id or "",
                }
            )

        if mime_type == "text/plain" and data:
            text_parts.append(decode_base64url(data))
        elif mime_type == "text/html" and data:
            html_parts.append(decode_base64url(data))

        for subpart in part.get("parts", []):
            walk(subpart)

    walk(payload)
    return "\n".join(text_parts), "\n".join(html_parts), attachments


class GmailDataUpdateCoordinator(DataUpdateCoordinator[GmailMessage | None]):
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        session: OAuth2Session,
        update_interval: timedelta,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self._entry = entry
        self._session = session
        self._seen_message_ids: OrderedDict[str, None] = OrderedDict()
        self._initial_run: bool = True
        self._queue: deque[GmailMessage] = deque()
        self._active_message: GmailMessage | None = None
        self._last_message: GmailMessage | None = None
        self._recent_emails: deque[GmailMessage] = deque(maxlen=MAX_RECENT_EMAILS)
        self._queue_task: asyncio.Task[None] | None = None
        self._unread_count: int = 0

    @property
    def unread_count(self) -> int:
        return self._unread_count

    @property
    def queue_size(self) -> int:
        return len(self._queue)

    @property
    def last_message(self) -> GmailMessage | None:
        return self._last_message

    @property
    def recent_emails(self) -> list[GmailMessage]:
        return list(self._recent_emails)

    def cancel_queue_task(self) -> None:
        if self._queue_task is not None and not self._queue_task.done():
            self._queue_task.cancel()
            self._queue_task = None

    def _record_seen(self, message_id: str) -> None:
        self._seen_message_ids[message_id] = None
        if len(self._seen_message_ids) > MAX_SEEN_CACHE_SIZE:
            self._seen_message_ids.popitem(last=False)

    async def _fetch_message_details(self, message_id: str) -> GmailMessage | None:
        url = f"{GMAIL_MESSAGES_URL}/{message_id}"
        params = {
            "format": "metadata",
            "metadataHeaders": ["From", "Subject", "Date"],
        }
        try:
            async with asyncio.timeout(10):
                resp = await self._session.async_request("GET", url, params=params)
                if resp.status in (400, 401):
                    raise ConfigEntryAuthFailed(
                        f"Authentication failed fetching message {message_id}: {resp.status}"
                    )
                if resp.status in (429, 503):
                    raise UpdateFailed(
                        f"Rate limited or server error fetching message {message_id}: {resp.status}"
                    )
                if resp.status != 200:
                    return None
                data = await resp.json()
        except TimeoutError as err:
            raise UpdateFailed(f"Timeout fetching message {message_id}: {err}") from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Network error fetching message {message_id}: {err}") from err

        headers = {
            header.get("name", "").lower(): header.get("value", "")
            for header in data.get("payload", {}).get("headers", [])
        }
        raw_from = headers.get("from", "")
        raw_subject = headers.get("subject", "")
        raw_date = headers.get("date", "")
        raw_snippet = data.get("snippet", "")

        display_sender, sender_name, sender_email = parse_sender_components(raw_from)
        subject = decode_mime_header(raw_subject)
        body_preview = sanitize_text(raw_snippet, MAX_BODY_PREVIEW_LENGTH)
        received_time = parse_email_date(raw_date)

        return GmailMessage(
            message_id=message_id,
            sender=display_sender,
            sender_name=sender_name,
            sender_email=sender_email,
            subject=subject,
            body_preview=body_preview,
            received_time=received_time,
        )

    async def _async_update_data(self) -> GmailMessage | None:
        query = self._entry.options.get(CONF_QUERY, DEFAULT_QUERY)
        params = {"q": query, "maxResults": "20"}
        try:
            async with asyncio.timeout(10):
                resp = await self._session.async_request(
                    "GET", GMAIL_MESSAGES_URL, params=params
                )
                if resp.status in (400, 401):
                    raise ConfigEntryAuthFailed(
                        f"Authentication failed querying messages: {resp.status}"
                    )
                if resp.status in (429, 503):
                    raise UpdateFailed(
                        f"Gmail API rate limited or server error: {resp.status}"
                    )
                if resp.status != 200:
                    raise UpdateFailed(
                        f"Unexpected response querying messages: {resp.status}"
                    )
                data = await resp.json()
        except TimeoutError as err:
            raise UpdateFailed(f"Timeout querying messages: {err}") from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Network error querying messages: {err}") from err

        messages = data.get("messages", [])
        self._unread_count = len(messages)

        if self._initial_run:
            for message_summary in messages:
                self._record_seen(message_summary["id"])
            for message_summary in reversed(messages[:MAX_RECENT_EMAILS]):
                details = await self._fetch_message_details(message_summary["id"])
                if details is not None:
                    self._recent_emails.append(details)
                    self._last_message = details
            self._initial_run = False
            return self._active_message

        new_messages: list[GmailMessage] = []
        for message_summary in reversed(messages):
            message_id = message_summary["id"]
            if message_id not in self._seen_message_ids:
                self._record_seen(message_id)
                details = await self._fetch_message_details(message_id)
                if details is not None:
                    new_messages.append(details)

        for message in new_messages:
            self._queue.append(message)

        if self._queue and (self._queue_task is None or self._queue_task.done()):
            self._queue_task = self.hass.async_create_background_task(
                self._process_queue(), "gmail_queue_processor"
            )

        return self._active_message

    async def _process_queue(self) -> None:
        dwell_time = self._entry.options.get(
            CONF_QUEUE_DWELL_TIME, DEFAULT_QUEUE_DWELL_TIME
        )
        try:
            while self._queue:
                self._active_message = self._queue.popleft()
                self._last_message = self._active_message
                self._recent_emails.append(self._active_message)
                self.hass.bus.async_fire(
                    "gmail_oauth_reader_new_email", asdict(self._active_message)
                )
                self.async_set_updated_data(self._active_message)
                await asyncio.sleep(dwell_time)
        finally:
            self._active_message = None
            self.async_set_updated_data(None)

    async def async_get_full_email(self, message_id: str) -> dict[str, Any]:
        url = f"{GMAIL_MESSAGES_URL}/{message_id}"
        params = {"format": "full"}
        try:
            async with asyncio.timeout(15):
                resp = await self._session.async_request("GET", url, params=params)
                if resp.status in (400, 401):
                    raise ConfigEntryAuthFailed(
                        f"Authentication failed fetching full email {message_id}: {resp.status}"
                    )
                if resp.status != 200:
                    raise HomeAssistantError(
                        f"Failed to fetch full email {message_id}: {resp.status}"
                    )
                data = await resp.json()
        except TimeoutError as err:
            raise HomeAssistantError(
                f"Timeout fetching full email {message_id}: {err}"
            ) from err
        except aiohttp.ClientError as err:
            raise HomeAssistantError(
                f"Network error fetching full email {message_id}: {err}"
            ) from err

        payload = data.get("payload", {})
        raw_headers = {
            header.get("name", ""): header.get("value", "")
            for header in payload.get("headers", [])
        }
        headers_lower = {name.lower(): value for name, value in raw_headers.items()}

        display_sender, sender_name, sender_email = parse_sender_components(
            headers_lower.get("from", "")
        )
        subject = decode_mime_header(headers_lower.get("subject", ""))
        received_time = parse_email_date(headers_lower.get("date", ""))
        text_body, html_body, attachments = extract_mime_bodies_and_attachments(payload)

        return {
            "message_id": message_id,
            "thread_id": data.get("threadId", ""),
            "sender": display_sender,
            "sender_name": sender_name,
            "sender_email": sender_email,
            "to": headers_lower.get("to", ""),
            "cc": headers_lower.get("cc", ""),
            "bcc": headers_lower.get("bcc", ""),
            "subject": subject,
            "date": received_time,
            "labels": data.get("labelIds", []),
            "snippet": data.get("snippet", ""),
            "text_body": text_body,
            "html_body": html_body,
            "attachments": attachments,
            "headers": raw_headers,
        }

    async def async_modify_email(
        self,
        message_id: str,
        add_labels: list[str] | None = None,
        remove_labels: list[str] | None = None,
    ) -> dict[str, Any]:
        url = f"{GMAIL_MESSAGES_URL}/{message_id}/modify"
        payload = {
            "addLabelIds": add_labels or [],
            "removeLabelIds": remove_labels or [],
        }
        try:
            async with asyncio.timeout(10):
                resp = await self._session.async_request("POST", url, json=payload)
                if resp.status in (400, 401):
                    raise ConfigEntryAuthFailed(
                        f"Authentication failed modifying email {message_id}: {resp.status}"
                    )
                if resp.status != 200:
                    raise HomeAssistantError(
                        f"Failed modifying email {message_id}: {resp.status}"
                    )
                data = await resp.json()
        except TimeoutError as err:
            raise HomeAssistantError(
                f"Timeout modifying email {message_id}: {err}"
            ) from err
        except aiohttp.ClientError as err:
            raise HomeAssistantError(
                f"Network error modifying email {message_id}: {err}"
            ) from err

        return {
            "message_id": message_id,
            "labels": data.get("labelIds", []),
        }

    async def async_download_attachment(
        self, message_id: str, attachment_id: str
    ) -> bytes:
        url = f"{GMAIL_MESSAGES_URL}/{message_id}/attachments/{attachment_id}"
        try:
            async with asyncio.timeout(15):
                resp = await self._session.async_request("GET", url)
                if resp.status in (400, 401):
                    raise ConfigEntryAuthFailed(
                        f"Authentication failed downloading attachment: {resp.status}"
                    )
                if resp.status != 200:
                    raise HomeAssistantError(
                        f"Failed downloading attachment: {resp.status}"
                    )
                data = await resp.json()
        except TimeoutError as err:
            raise HomeAssistantError(
                f"Timeout downloading attachment: {err}"
            ) from err
        except aiohttp.ClientError as err:
            raise HomeAssistantError(
                f"Network error downloading attachment: {err}"
            ) from err

        raw_data = data.get("data", "")
        padding = 4 - (len(raw_data) % 4)
        if padding and padding < 4:
            raw_data += "=" * padding
        return base64.urlsafe_b64decode(raw_data.encode("ascii"))
