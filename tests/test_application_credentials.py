from homeassistant.core import HomeAssistant

from custom_components.gmail_oauth_reader.application_credentials import (
    async_get_authorization_server,
    async_get_description_placeholders,
)


async def test_application_credentials_authorization_server(hass: HomeAssistant) -> None:
    server = await async_get_authorization_server(hass)
    assert server.authorize_url == 'https://accounts.google.com/o/oauth2/v2/auth'
    assert server.token_url == 'https://oauth2.googleapis.com/token'


async def test_application_credentials_description_placeholders(hass: HomeAssistant) -> None:
    placeholders = await async_get_description_placeholders(hass)
    assert 'oauth_url' in placeholders
    assert placeholders['oauth_url'] == 'https://my.home-assistant.io/redirect/oauth'
    assert 'more_info_url' in placeholders
