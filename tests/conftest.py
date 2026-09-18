from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock
import pytest

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

import socket
import pytest_socket

socket.socket = pytest_socket._true_socket
pytest_socket.disable_socket = lambda *args, **kwargs: None

from custom_components.gmail_oauth_reader.const import (
    CONF_ENABLE_WRITE,
    CONF_EXTRACT_OTP,
    CONF_OTP_EXPIRY_MINUTES,
    CONF_POLL_INTERVAL,
    CONF_QUEUE_DWELL_TIME,
    DEFAULT_ENABLE_WRITE,
    DEFAULT_EXTRACT_OTP,
    DEFAULT_OTP_EXPIRY_MINUTES,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_QUEUE_DWELL_TIME,
    DOMAIN,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> Generator[None, None, None]:
    pytest_socket.enable_socket()
    yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="test_user@gmail.com",
        title="test_user@gmail.com",
        data={
            "auth_implementation": "google",
            "token": {
                "access_token": "mock_access_token",
                "refresh_token": "mock_refresh_token",
                "expires_at": 9999999999,
            },
            CONF_ENABLE_WRITE: DEFAULT_ENABLE_WRITE,
        },
        options={
            CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL,
            CONF_QUEUE_DWELL_TIME: DEFAULT_QUEUE_DWELL_TIME,
            CONF_EXTRACT_OTP: DEFAULT_EXTRACT_OTP,
            CONF_OTP_EXPIRY_MINUTES: DEFAULT_OTP_EXPIRY_MINUTES,
            CONF_ENABLE_WRITE: DEFAULT_ENABLE_WRITE,
        },
        entry_id="test_entry_id",
    )


@pytest.fixture
def mock_oauth_session() -> MagicMock:
    session = MagicMock()
    session.async_ensure_token_valid = AsyncMock(return_value=True)
    session.async_request = AsyncMock()
    return session
