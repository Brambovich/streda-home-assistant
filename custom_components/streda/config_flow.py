"""Config flow for streda Lights integration."""

import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .api import StredaApiClient
from .const import CONF_REFRESH_TOKEN, CONF_LOCATION_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _normalize_refresh_token(raw_token: str) -> str:
    """Accept plain tokens or secret:\"<TOKEN>\" format."""
    if raw_token.startswith("secret:"):
        token = raw_token[len("secret:") :].strip()
        # Remove surrounding quotes if present
        if token.startswith('"') and token.endswith('"'):
            token = token[1:-1]
        return token
    return raw_token


def _normalize_location_id(raw_token: str) -> str:
    """Accept plain id or locationId:\"<id>\" format."""
    if raw_token.startswith("locationId:"):
        token = raw_token[len("locationId:") :].strip()
        # Remove surrounding quotes if present
        if token.startswith('"') and token.endswith('"'):
            token = token[1:-1]
        return token
    return raw_token


async def validate_input(hass: HomeAssistant, data: dict) -> dict:
    """Validate the user input allows us to connect."""
    session = async_get_clientsession(hass)

    refresh_token = _normalize_refresh_token(data[CONF_REFRESH_TOKEN])
    location_id = _normalize_location_id(data[CONF_LOCATION_ID])

    api_client = StredaApiClient(refresh_token, location_id, session)

    # Verify the user has access to the location
    if not await api_client.verify_access():
        raise Exception("Cannot verify access to location")

    return {CONF_REFRESH_TOKEN: refresh_token, CONF_LOCATION_ID: location_id}


class StredaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for streda Lights."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the user step - refresh token and location ID."""
        errors = {}

        if user_input is not None:
            try:
                normalized_data = await validate_input(self.hass, user_input)
                return self.async_create_entry(
                    title="Streda integration", data=normalized_data
                )
            except Exception as err:
                _LOGGER.exception("Failed to verify access: %s", err)
                errors["base"] = "cannot_connect"

        data_schema = vol.Schema(
            {
                vol.Required(CONF_REFRESH_TOKEN): cv.string,
                vol.Required(CONF_LOCATION_ID): cv.string,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "refresh_token_help": "Enter your refresh token from the provider",
                "location_id_help": "Enter your location ID",
            },
        )
