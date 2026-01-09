"""API client for streda provider."""

import asyncio
import logging
import aiohttp
import async_timeout
from datetime import datetime, timedelta, timezone


from .const import (
    STREDA_AUTHENTICATION_API_URL,
    CLIENT_ID,
    STREDA_B2C_TOKEN_URL,
    STREDA_DATA_API_URL,
    STREDA_SIGNALR_NEGOTIATE_URL,
)

_LOGGER = logging.getLogger(__name__)


class StredaApiClient:
    """API client for communicating with streda provider."""

    def __init__(
        self,
        refresh_token: str,
        location_id: str,
        session: aiohttp.ClientSession,
        token_update_callback: callable = None,
    ):
        """Initialize the API client."""
        _LOGGER.info("Initializing StredaApiClient, %s", location_id)

        self._refresh_token = refresh_token
        self._token_update_callback = token_update_callback
        self._location_id = location_id
        self._session = session
        self._id_token = None
        self._api_token = None
        self._expiry_date = None

    async def verify_token_validity(self) -> bool:
        """Verify if the current token is still valid."""
        if self._expiry_date is None:
            return False
        now = datetime.now(timezone.utc)
        _LOGGER.debug(
            "Token expiry date: %s, now: %s, diff: %s",
            self._expiry_date,
            now,
            self._expiry_date - now,
        )
        return now < (
            self._expiry_date - timedelta(hours=1)
        )  # Consider token invalid if less than 1 hour left

    async def reauthenticate_if_needed(self) -> bool:
        """Re-authenticate if the token is expired or about to expire."""
        if not await self.verify_token_validity():
            _LOGGER.debug("Token expired or invalid, re-authenticating")
            await self.authenticate_b2c()
            await self.authenticate_api()
            return True
        return False

    async def authenticate_b2c(self) -> bool:
        """Authenticate and get id token using refresh token."""
        try:
            async with async_timeout.timeout(10):
                url = STREDA_B2C_TOKEN_URL

                payload = {
                    "client_id": CLIENT_ID,
                    "refresh_token": self._refresh_token,
                    "grant_type": "refresh_token",
                    "scope": f"openid offline_access {CLIENT_ID}",
                }

                async with self._session.post(url, data=payload) as response:
                    response.raise_for_status()
                    data = await response.json()

                    self._id_token = data.get("id_token")
                    self._refresh_token = data.get("refresh_token")

                    # Save the new refresh token
                    if self._token_update_callback:
                        await self._token_update_callback(self._refresh_token)

                    if not self._id_token:
                        _LOGGER.error("No ID token in response")
                        return False

                    _LOGGER.debug("Successfully authenticated b2c token.")
                    return True

        except aiohttp.ClientError as err:
            _LOGGER.error("Authentication failed: %s", err)
            return False
        except Exception as err:
            _LOGGER.error("Unexpected authentication error: %s", err)
            return False

    async def authenticate_api(self) -> bool:
        """Authenticate and get api access token using refresh token."""
        try:
            async with async_timeout.timeout(10):
                url = f"{STREDA_AUTHENTICATION_API_URL}/UserAuth/login"

                async with self._session.post(url, json=self._id_token) as response:
                    response.raise_for_status()
                    data = await response.json()
                    self._api_token = data.get("token")

                    if not self._api_token:
                        _LOGGER.error("No API token in response")
                        return False

                    dt = datetime.now(timezone.utc)
                    dt_plus = dt + timedelta(seconds=data.get("expiresInSeconds", 0))
                    self._expiry_date = dt_plus

                    _LOGGER.debug(
                        "Successfully authenticated API token, new expiry: %s",
                        self._expiry_date,
                    )
                    return True

        except aiohttp.ClientError as err:
            _LOGGER.error("Authentication failed: %s", err)
            return False
        except Exception as err:
            _LOGGER.error("Unexpected authentication error: %s", err)
            return False

    async def get_signalr_access_token(self) -> str:
        """Get SignalR access token using api token."""
        try:
            async with async_timeout.timeout(10):
                negotiate_headers = {"Authorization": f"Bearer {self._api_token}"}

                async with self._session.post(
                    STREDA_SIGNALR_NEGOTIATE_URL, headers=negotiate_headers
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    token = data.get("accessToken")

                    if not token:
                        _LOGGER.error("No SignalR access token in response")
                        return False
                    _LOGGER.debug("Successfully retrieved SignalR access token")
                    return token

        except aiohttp.ClientError as err:
            _LOGGER.error("Authentication failed: %s", err)
            return ""
        except Exception as err:
            _LOGGER.error("Unexpected authentication error: %s", err)
            return ""

    async def verify_access(self) -> bool:
        """Verify user has access to the location."""
        try:
            # First authenticate to get access token
            if not await self.authenticate_b2c():
                return False

            if not await self.authenticate_api():
                return False

            async with async_timeout.timeout(10):
                headers = {
                    "Authorization": f"Bearer {self._api_token}",
                    "Content-Type": "application/json",
                }

                # Check if user has access to this location
                url = f"{STREDA_DATA_API_URL}/Location/{self._location_id}"

                async with self._session.get(url, headers=headers) as response:
                    if response.status == 404:
                        _LOGGER.error("Location not found")
                        return False
                    elif response.status == 403:
                        _LOGGER.error("No access to location")
                        return False

                    response.raise_for_status()
                    _LOGGER.debug("Successfully verified access to location")
                    return True

        except aiohttp.ClientError as err:
            _LOGGER.error("Error verifying access: %s", err)
            return False
        except Exception as err:
            _LOGGER.error("Unexpected error verifying access: %s", err)
            return False

    async def get_device_states(self) -> list[dict]:
        """Fetch all device states from the API."""
        if not self._api_token:
            await self.verify_access()

        try:
            async with async_timeout.timeout(10):
                headers = {
                    "Authorization": f"Bearer {self._api_token}",
                    "Content-Type": "application/json",
                }

                url = f"{STREDA_DATA_API_URL}/DeviceState/{self._location_id}/deviceStates"

                async with self._session.get(url, headers=headers) as response:
                    response.raise_for_status()
                    data = await response.json()

                    return data if isinstance(data, list) else []

        except aiohttp.ClientError as err:
            _LOGGER.error("Error fetching lights: %s", err)
            raise
        except Exception as err:
            _LOGGER.error("Unexpected error fetching lights: %s", err)
            raise

    async def discover_system(self) -> list[dict]:
        """Fetch all device discovery information from the API."""
        if not self._api_token:
            await self.verify_access()

        try:
            async with async_timeout.timeout(20):
                headers = {
                    "Authorization": f"Bearer {self._api_token}",
                    "Content-Type": "application/json",
                }

                async def fetch(url):
                    async with self._session.get(url, headers=headers) as response:
                        response.raise_for_status()
                        return await response.json()

                ROOMS_URL = f"https://streda-admin-production.azurewebsites.net/Room/{self._location_id}/getRooms"
                rooms_data = await fetch(ROOMS_URL)

                async def fetch_docks_for_room(room):
                    docks_url = f"https://streda-admin-production.azurewebsites.net/Dock/{self._location_id}/{room.get('id')}/getDocks"
                    docks = await fetch(docks_url)
                    return {
                        "room_id": room.get("id"),
                        "room_name": room.get("name"),
                        "docks": docks,
                    }

                results = await asyncio.gather(
                    *(fetch_docks_for_room(room) for room in rooms_data)
                )
                return results

        except aiohttp.ClientError as err:
            _LOGGER.error("Error fetching system discovery: %s", err)
            raise
        except Exception as err:
            _LOGGER.error("Unexpected error fetching system discovery: %s", err)
            raise

    async def toggle_light(self, dock_number: int, dock_device_number: int) -> bool:
        """Turn a light on or off."""
        try:
            async with async_timeout.timeout(10):
                headers = {
                    "Authorization": f"Bearer {self._api_token}",
                    "Content-Type": "application/json",
                }

                # Adjust endpoint and payload to match your API
                url = (
                    f"{STREDA_DATA_API_URL}/DeviceState/{self._location_id}/deviceState"
                )
                payload = {
                    "action": "ActionSwitch",
                    "actionParameters": {"switchAction": "TOGGLE"},
                    "targetDevice": {
                        "deviceNumber": dock_device_number,
                        "dockNumber": f"{str(dock_number)}",
                    },
                }

                async with self._session.post(
                    url, headers=headers, json=payload
                ) as response:
                    response.raise_for_status()
                    return True

        except aiohttp.ClientError as err:
            _LOGGER.error("Error setting light state: %s", err)
            return False
        except Exception as err:
            _LOGGER.error("Unexpected error setting light state: %s", err)
            return False
        _LOGGER.error("Expected error setting light state")
        return False
