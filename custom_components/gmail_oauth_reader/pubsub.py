import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
import logging
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session

from .const import (
    GMAIL_STOP_URL,
    GMAIL_WATCH_URL,
    PUBSUB_BASE_URL,
    WATCH_RENEWAL_DAYS,
)

_LOGGER = logging.getLogger(__name__)


def parse_pubsub_expiration(expiration_ms: str | int | None) -> datetime | None:
    if not expiration_ms:
        return None
    try:
        timestamp_s = int(expiration_ms) / 1000.0
        return datetime.fromtimestamp(timestamp_s, tz=timezone.utc)
    except (ValueError, TypeError):
        return None


def format_subscription_path(project_id: str, subscription_name: str) -> str:
    cleaned_project = project_id.strip()
    cleaned_sub = subscription_name.strip()
    if cleaned_sub.startswith("projects/"):
        return cleaned_sub
    return f"projects/{cleaned_project}/subscriptions/{cleaned_sub}"


def format_topic_path(project_id: str, topic_name: str) -> str:
    cleaned_project = project_id.strip()
    cleaned_topic = topic_name.strip()
    if cleaned_topic.startswith("projects/"):
        return cleaned_topic
    return f"projects/{cleaned_project}/topics/{cleaned_topic}"


class GmailWatchManager:
    def __init__(self, hass: HomeAssistant, session: OAuth2Session) -> None:
        self._hass = hass
        self._session = session
        self._watch_active: bool = False
        self._watch_expiration: datetime | None = None
        self._history_id: str | None = None
        self._renewal_task: asyncio.Task[None] | None = None

    @property
    def watch_active(self) -> bool:
        return self._watch_active

    @property
    def watch_expiration(self) -> datetime | None:
        return self._watch_expiration

    @property
    def history_id(self) -> str | None:
        return self._history_id

    async def async_start_watch(self, topic_path: str) -> bool:
        self._cancel_renewal()
        success = await self._async_call_watch_api(topic_path)
        if success:
            self._renewal_task = self._hass.async_create_background_task(
                self._async_renewal_loop(topic_path),
                "gmail_watch_renewal_loop",
            )
        return success

    async def async_stop_watch(self) -> None:
        self._cancel_renewal()
        if not self._watch_active:
            return
        try:
            async with asyncio.timeout(10):
                await self._session.async_request("POST", GMAIL_STOP_URL)
        except Exception as err:
            _LOGGER.warning("Error stopping Gmail watch: %s", err)
        finally:
            self._watch_active = False
            self._watch_expiration = None
            self._history_id = None

    def _cancel_renewal(self) -> None:
        if self._renewal_task is not None and not self._renewal_task.done():
            self._renewal_task.cancel()
            self._renewal_task = None

    async def _async_call_watch_api(self, topic_path: str) -> bool:
        payload = {
            "topicName": topic_path,
            "labelIds": ["INBOX"],
        }
        try:
            async with asyncio.timeout(15):
                resp = await self._session.async_request(
                    "POST", GMAIL_WATCH_URL, json=payload
                )
                if resp.status != 200:
                    body = await resp.text()
                    _LOGGER.error(
                        "Failed to start Gmail watch: %s (%s)", resp.status, body
                    )
                    self._watch_active = False
                    return False

                data: dict[str, Any] = await resp.json()
                self._history_id = str(data.get("historyId", ""))
                self._watch_expiration = parse_pubsub_expiration(
                    data.get("expiration")
                )
                self._watch_active = True
                _LOGGER.info(
                    "Gmail watch active until %s", self._watch_expiration
                )
                return True
        except Exception as err:
            _LOGGER.error("Exception starting Gmail watch: %s", err)
            self._watch_active = False
            return False

    async def _async_renewal_loop(self, topic_path: str) -> None:
        try:
            while True:
                sleep_seconds = WATCH_RENEWAL_DAYS * 86400
                await asyncio.sleep(sleep_seconds)
                _LOGGER.debug("Renewing Gmail watch for topic %s", topic_path)
                await self._async_call_watch_api(topic_path)
        except asyncio.CancelledError:
            pass


class PubSubPullListener:
    def __init__(self, hass: HomeAssistant, session: OAuth2Session) -> None:
        self._hass = hass
        self._session = session
        self._pull_task: asyncio.Task[None] | None = None
        self._is_running: bool = False

    @property
    def is_running(self) -> bool:
        return self._is_running

    def start(
        self,
        subscription_path: str,
        on_notification: Callable[[], Awaitable[None]],
    ) -> None:
        self.stop()
        self._is_running = True
        self._pull_task = self._hass.async_create_background_task(
            self._pull_loop(subscription_path, on_notification),
            "gmail_pubsub_pull_listener",
        )

    def stop(self) -> None:
        self._is_running = False
        if self._pull_task is not None and not self._pull_task.done():
            self._pull_task.cancel()
            self._pull_task = None

    async def _pull_loop(
        self,
        subscription_path: str,
        on_notification: Callable[[], Awaitable[None]],
    ) -> None:
        pull_url = f"{PUBSUB_BASE_URL}/{subscription_path}:pull"
        ack_url = f"{PUBSUB_BASE_URL}/{subscription_path}:acknowledge"
        backoff = 2

        while self._is_running:
            try:
                payload = {"maxMessages": 10}
                async with asyncio.timeout(30):
                    resp = await self._session.async_request(
                        "POST", pull_url, json=payload
                    )

                if resp.status == 200:
                    backoff = 2
                    data: dict[str, Any] = await resp.json()
                    received_messages = data.get("receivedMessages", [])
                    if received_messages:
                        ack_ids = [
                            msg["ackId"]
                            for msg in received_messages
                            if "ackId" in msg
                        ]
                        if ack_ids:
                            await self._session.async_request(
                                "POST", ack_url, json={"ackIds": ack_ids}
                            )
                        await on_notification()
                    else:
                        await asyncio.sleep(1)
                elif resp.status in (401, 403):
                    _LOGGER.error(
                        "Pub/Sub pull authorization error %s. Pausing pull listener.",
                        resp.status,
                    )
                    await asyncio.sleep(60)
                else:
                    _LOGGER.warning(
                        "Pub/Sub pull received status %s. Retrying in %ss",
                        resp.status,
                        backoff,
                    )
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 60)

            except asyncio.CancelledError:
                break
            except TimeoutError:
                continue
            except aiohttp.ClientError as err:
                _LOGGER.debug("Pub/Sub pull network error: %s", err)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
            except Exception as err:
                _LOGGER.error("Unexpected error in Pub/Sub pull loop: %s", err)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
