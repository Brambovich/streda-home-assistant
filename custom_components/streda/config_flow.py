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


async def validate_input(hass: HomeAssistant, data: dict) -> dict:
    """Validate the user input allows us to connect."""
    session = async_get_clientsession(hass)
    api_client = StredaApiClient(
        data[CONF_REFRESH_TOKEN], data[CONF_LOCATION_ID], session
    )

    # Verify the user has access to the location
    if not await api_client.verify_access():
        raise Exception("Cannot verify access to location")

    return {"title": f"Streda integration"}


class StredaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for streda Lights."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the user step - refresh token and location ID."""
        errors = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
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
