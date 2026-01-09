"""Data update coordinator for streda Lights."""

import asyncio
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant, callback
from signalrcore.hub_connection_builder import HubConnectionBuilder
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import StredaApiClient
from .const import DOMAIN, STREDA_SIGNALR_HUB_URL

_LOGGER = logging.getLogger(__name__)


class DataCoordinator(DataUpdateCoordinator):
    """Coordinator to setup the SignalR connection and manage as backup fetching data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: StredaApiClient,
        location_id: str,
        update_interval: int,
    ):
        """Initialize the coordinator."""
        self.api_client = api_client
        self.hub_connection = None
        self.location_id = location_id

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval),
        )

    async def _async_update_data(self):
        """Check token validity and fetch data from API."""
        try:
            device_states = await self.api_client.get_device_states()
            self.async_set_updated_data({"device_states": device_states})
            return self.data or {"device_states": []}
        except Exception as err:
            raise UpdateFailed(
                f"Error refreshing b2c token or api token: {err}"
            ) from err

    async def async_start_signalr(self):
        """Start SignalR connection."""
        try:
            # Get initial data
            device_states = await self.api_client.get_device_states()
            self.async_set_updated_data({"device_states": device_states})

            # Build SignalR connection
            signalr_access_token = await self.api_client.get_signalr_access_token()
            self.hub_connection = (
                HubConnectionBuilder()
                .with_url(
                    STREDA_SIGNALR_HUB_URL,
                    options={
                        "access_token_factory": lambda: signalr_access_token,
                    },
                )
                .with_automatic_reconnect(
                    {
                        "type": "interval",
                        "intervals": [0, 2, 10, 30],  # Reconnect intervals in seconds
                    }
                )
                .build()
            )

            # Register event handlers
            self.hub_connection.on_open(self._on_signalr_open)
            self.hub_connection.on_close(self._on_signalr_close)
            self.hub_connection.on_error(self._on_signalr_error)

            # Register message handlers for device updates
            self.hub_connection.on(
                "deviceStateNotification",
                lambda data: self.hass.loop.call_soon_threadsafe(
                    self._handle_device_update, data
                ),
            )

            # Start connection in background
            await self.hass.async_add_executor_job(self.hub_connection.start)
            _LOGGER.info("SignalR connection started successfully")

        except Exception as err:
            _LOGGER.error(f"Failed to start SignalR connection: {err}")
            raise

    async def _reconnect_signalr(self):
        """Reconnect SignalR with fresh token."""
        try:
            # Stop existing connection
            if self.hub_connection:
                await self.hass.async_add_executor_job(self.hub_connection.stop)
                self._signalr_connected = False

            # Wait a moment
            await asyncio.sleep(1)

            # Start new connection with fresh token
            await self.async_start_signalr()

        except Exception as err:
            _LOGGER.error(f"Failed to reconnect SignalR: {err}")

    @callback
    def _on_signalr_open(self):
        """Handle SignalR connection opened."""
        _LOGGER.info("SignalR connection opened")
        self.hub_connection.send(
            "SubscribeDeviceStatesForLocationAsync", [self.location_id]
        )

    @callback
    def _on_signalr_close(self):
        """Handle SignalR connection closed."""
        _LOGGER.warning("SignalR connection closed")

    @callback
    def _on_signalr_error(self, data):
        """Handle SignalR errors."""
        _LOGGER.error(f"SignalR error: {data}")

    @callback
    def _handle_device_update(self, message):
        """Handle general device updates from SignalR."""
        try:
            # Similar logic to _handle_device_state_change
            current_data = self.data.get("device_states", [])

            # Find and update the device
            self.apply_signalr_updates(current_data, message)

            # Trigger update to all entities
            self.async_set_updated_data({"device_states": current_data})
        except Exception as err:
            _LOGGER.error(f"Error handling device update: {err}")

    async def async_stop_signalr(self):
        """Stop SignalR connection."""
        if self.hub_connection:
            try:
                await self.hass.async_add_executor_job(self.hub_connection.stop)
                _LOGGER.info("SignalR connection stopped")
            except Exception as err:
                _LOGGER.error(f"Error stopping SignalR: {err}")
            finally:
                self.hub_connection = None

    def apply_signalr_updates(
        self, full_state: list[dict], updates: list[dict]
    ) -> None:
        """
        Mutates full_state by applying SignalR updates.
        """

        # Index SnapIns by zigbeeId
        snapin_index = {}
        for snapin in full_state:
            zigbee_id = snapin.get("zigbeeId")
            if zigbee_id:
                snapin_index[zigbee_id] = snapin

        for update in updates:
            zigbee_id = update.get("zigbeeId")
            device_number = update.get("deviceNumber")
            device_state = update.get("deviceState")

            if not (zigbee_id and device_state):
                continue

            snapin = snapin_index.get(zigbee_id)
            if not snapin:
                continue

            # Index devices for this SnapIn
            devices = snapin.get("devices", [])
            device = next(
                (d for d in devices if d.get("deviceNumber") == device_number), None
            )
            if not device:
                continue

            state_type = device_state.get("type")
            state_data = device_state.get("data", {})

            # Find or create state
            for state in device.get("states", []):
                if state.get("type") == state_type:
                    state["data"].update(state_data)
                    break
            return
