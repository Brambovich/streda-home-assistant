"""Switch platform for Smart Plug integration."""

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, POSITION_DESCRIPTIONS
from .coordinator import DataCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch platform."""
    data_coordinator: DataCoordinator = hass.data[DOMAIN][entry.entry_id][
        "data_coordinator"
    ]

    # Get devices from coordinator data
    system = hass.data[DOMAIN][entry.entry_id]["system"]

    entities = []
    for room in system:
        for dock in room.get("docks", []):
            # only add lights for now.
            if dock.get("dockCode") != "BN1-C":
                continue
            entities.append(RelayBin(data_coordinator, room, dock))

    _LOGGER.info("Setting up %d switch entities", len(entities))
    async_add_entities(entities)


class RelayBin(CoordinatorEntity, SwitchEntity):
    """Representation of a Smart Plug Socket."""

    def __init__(
        self, data_coordinator: DataCoordinator, room_data: dict, dock_data: dict
    ) -> None:
        """Initialize the socket."""
        super().__init__(data_coordinator)

        # Dock information
        self._zigbee_id = dock_data.get("zigbeeId")
        self._snap_in_id = dock_data.get("snapInId")
        self._dock_number = dock_data.get("number")
        self._dock_device_number = None  # to be filled later

        # Room information
        self._room_name = room_data.get("room_name", "Unknown")
        self._room_id = room_data.get("room_id")

        # Entity attributes
        self._attr_name = f"{self._room_name} Ceiling Light"
        self._attr_unique_id = (
            f"{DOMAIN}_{self._snap_in_id}_relay_{self._dock_device_number}"
        )

        # Firmware version and device number
        devices = self.coordinator.data.get("device_states", [])
        for snap_in in devices:
            if snap_in.get("zigbeeId") == self._zigbee_id:
                # Firmware version snap in
                firmware_state = next(
                    (
                        state
                        for state in snap_in.get("states", [])
                        if state.get("type") == "FirmwareState"
                    ),
                    None,
                )
                if firmware_state:
                    firmware_version = firmware_state.get("data", {}).get(
                        "firmwareVersion", "unknown"
                    )
                # device number in dock
                for device in snap_in.get("devices", []):
                    if device.get("deviceType") == "RelayBin":
                        self._dock_device_number = device.get("deviceNumber")
                break

        # Device info - this groups entities together
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._snap_in_id)},
            name=f"{self._room_name} {POSITION_DESCRIPTIONS.get(dock_data.get('positionId', ''), '')}",
            manufacturer="Isolectra",
            model="Ceiling mounted snap-in",
            sw_version=firmware_version,
        )

    @property
    def snap_in_data(self) -> dict:
        """Get current socket data from coordinator."""
        devices = self.coordinator.data.get("device_states", [])
        for snap_in in devices:
            if snap_in.get("zigbeeId") == self._zigbee_id:
                return snap_in
        return {}

    @property
    def is_on(self) -> bool:
        """Return true if socket is on."""
        snap_in = self.snap_in_data
        for device in snap_in.get("devices", []):
            if device.get("deviceType") == "RelayBin":
                for state in device.get("states", []):
                    if state.get("type") == "PowerState":
                        state = state.get("data").get("state")
        return state == "ON"

    @property
    def icon(self):
        if self.is_on:
            return "mdi:ceiling-light"
        return "mdi:ceiling-light-outline"

    async def toggle(self, **kwargs: Any) -> None:
        """Turn the socket on."""
        await self.coordinator.api_client.toggle_light(
            self._dock_number, self._dock_device_number
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the socket on."""
        if not self.is_on:
            await self.toggle()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the socket off."""
        if self.is_on:
            await self.toggle()
