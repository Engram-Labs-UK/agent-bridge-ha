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
    coordinator: AgentBridgeCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    async_add_entities(
        [
            BridgeConnectedSensor(coordinator, entry),
        ]
    )


class BridgeConnectedSensor(
    CoordinatorEntity[AgentBridgeCoordinator], BinarySensorEntity
):
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


class PerAgentHealthSensor(
    CoordinatorEntity[AgentBridgeCoordinator], BinarySensorEntity
):
    """Binary sensor showing per-agent health status."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(
        self,
        coordinator: AgentBridgeCoordinator,
        entry: ConfigEntry,
        agent_id: str,
        agent_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._agent_id = agent_id
        self._attr_unique_id = f"{entry.entry_id}_{agent_id}_healthy"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Agent Bridge",
            manufacturer="Engram Labs",
            model="Agent Bridge",
        )

    @property
    def name(self) -> str:
        """Return entity name."""
        return f"{self._agent_id} Healthy"

    @property
    def is_on(self) -> bool | None:
        """Return True if this agent is healthy."""
        if not self.coordinator.data:
            return None
        for agent in self.coordinator.data["agents"]:
            if agent["id"] == self._agent_id:
                return agent.get("healthy", False)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return agent details as attributes."""
        if not self.coordinator.data:
            return {}
        for agent in self.coordinator.data["agents"]:
            if agent["id"] == self._agent_id:
                return {
                    "adapter": agent.get("adapter", ""),
                }
        return {}

    @property
    def available(self) -> bool:
        """Return False if agent no longer exists in discovery."""
        if not self.coordinator.data:
            return False
        agent_ids = {a["id"] for a in self.coordinator.data["agents"]}
        return self._agent_id in agent_ids
