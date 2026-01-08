"""The streda Lights integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import StredaApiClient
from .const import CONF_REFRESH_TOKEN, CONF_LOCATION_ID, FALLBACK_DATA_POLL_INTERVAL, ACCESS_TOKEN_VALIDITY_CHECK_INTERVAL, DOMAIN
from .coordinator import DataCoordinator, ApiAccessCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up streda Lights from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Get configuration
    refresh_token = entry.data[CONF_REFRESH_TOKEN]
    location_id = entry.data[CONF_LOCATION_ID]

    # Create API client
    session = async_get_clientsession(hass)

    async def save_token_to_disk(new_refresh_token: str):
        """Update the refresh token in the config entry."""
        _LOGGER.debug("Updating stored refresh token")
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_REFRESH_TOKEN: new_refresh_token}
        )

    api_client = StredaApiClient(refresh_token, location_id, session, save_token_to_disk)

    # 🔍 One-time system discovery
    system = await api_client.discover_system()

    # Create coordinators
    data_coordinator = DataCoordinator(hass, api_client, location_id, FALLBACK_DATA_POLL_INTERVAL)
    api_access_coordinator = ApiAccessCoordinator(hass, api_client, data_coordinator, ACCESS_TOKEN_VALIDITY_CHECK_INTERVAL)

    # Fetch initial data
    await api_access_coordinator.async_config_entry_first_refresh()
    await data_coordinator.async_config_entry_first_refresh()

    # Store global data
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api_client,
        "data_coordinator": data_coordinator,
        "api_access_coordinator": api_access_coordinator,
        "system": system,   # <-- discovery data lives here
    }

    await data_coordinator.async_start_signalr()
    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    data_coordinator = hass.data[DOMAIN][entry.entry_id]['data_coordinator']
    await data_coordinator.async_stop_signalr()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
            hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok