"""Sensor platform for Agent Bridge."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AgentBridgeCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Agent Bridge sensor entities."""
    coordinator: AgentBridgeCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities(
        [
            BridgeStatusSensor(coordinator, entry),
            AgentCountSensor(coordinator, entry),
        ]
    )


class BridgeStatusSensor(CoordinatorEntity[AgentBridgeCoordinator], SensorEntity):
    """Sensor showing bridge health status (ok/degraded/error)."""

    _attr_has_entity_name = True
    _attr_translation_key = "bridge_status"

    def __init__(
        self,
        coordinator: AgentBridgeCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_bridge_status"
        self._attr_device_info = _device_info(entry)

    @property
    def name(self) -> str:
        """Return entity name."""
        return "Bridge Status"

    @property
    def native_value(self) -> str | None:
        """Return bridge status."""
        if self.coordinator.data:
            return self.coordinator.data["bridge_status"]
        return None

    @property
    def extra_state_attributes(self) -> dict[str, str | int | bool]:
        """Return version, uptime and the v4.36 tool-surface view as attributes."""
        if not self.coordinator.data:
            return {}
        data = self.coordinator.data
        attrs: dict[str, str | int | bool] = {
            "version": data["bridge_version"],
            "uptime_seconds": data["bridge_uptime"],
        }
        # US0028/AC4: surface the actuation diagnostics when /v1/health provides them.
        if data.get("tool_surface"):
            attrs["tool_surface"] = data["tool_surface"]
        if "read_only_safe" in data:
            attrs["read_only_safe"] = data["read_only_safe"]
        return attrs


class AgentCountSensor(CoordinatorEntity[AgentBridgeCoordinator], SensorEntity):
    """Sensor showing the number of healthy agents."""

    _attr_has_entity_name = True
    _attr_translation_key = "agent_count"

    def __init__(
        self,
        coordinator: AgentBridgeCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_agent_count"
        self._attr_device_info = _device_info(entry)

    @property
    def name(self) -> str:
        """Return entity name."""
        return "Agent Count"

    @property
    def native_value(self) -> int | None:
        """Return healthy agent count."""
        if self.coordinator.data:
            return self.coordinator.data["agent_count_healthy"]
        return None

    @property
    def extra_state_attributes(self) -> dict[str, int]:
        """Return total count as attribute."""
        if not self.coordinator.data:
            return {}
        return {"total": self.coordinator.data["agent_count_total"]}


def _device_info(entry: ConfigEntry) -> dict:
    """Return device info for the single Agent Bridge device."""
    from homeassistant.helpers.device_registry import DeviceInfo

    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Agent Bridge",
        manufacturer="Engram Labs",
        model="Agent Bridge",
        entry_type=None,
    )
