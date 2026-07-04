"""Binary sensor platform for Agent Bridge."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AgentBridgeCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Agent Bridge binary sensor entities."""
    coordinator: AgentBridgeCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities(
        [
            BridgeConnectedSensor(coordinator, entry),
        ]
    )


class BridgeConnectedSensor(CoordinatorEntity[AgentBridgeCoordinator], BinarySensorEntity):
    """Binary sensor showing bridge connectivity."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(
        self,
        coordinator: AgentBridgeCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_connected"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Agent Bridge",
            manufacturer="Engram Labs",
            model="Agent Bridge",
        )

    @property
    def name(self) -> str:
        """Return entity name."""
        return "Connected"

    @property
    def is_on(self) -> bool | None:
        """Return True if bridge is connected."""
        if self.coordinator.data:
            return self.coordinator.data["connected"]
        return None


# CR-0016: the dead PerAgentHealthSensor class (never instantiated) was culled;
# per-agent health lives on the coordinator data + the diagnostics download.
