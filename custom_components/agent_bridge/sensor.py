"""Sensor platform for Agent Bridge."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .conversation import _agents_from_entry, _is_voice_capable
from .coordinator import AgentBridgeCoordinator
from .helpers import agent_label


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Agent Bridge sensor entities."""
    coordinator: AgentBridgeCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities: list[SensorEntity] = [
        BridgeStatusSensor(coordinator, entry),
        AgentCountSensor(coordinator, entry),
    ]

    # CR-0009: per-agent token + cost sensors, on the same device as the agent's
    # conversation entity. Iterate the configured agents like conversation.py does.
    agents_by_id: dict[str, dict[str, Any]] = {}
    if coordinator.data:
        agents_by_id = {a["id"]: a for a in coordinator.data["agents"]}
    for agent_id, agent_name, subentry_id, _prompt in _agents_from_entry(entry):
        agent_info = agents_by_id.get(agent_id)
        if not _is_voice_capable(agent_info):
            continue
        display_name = agent_label(agent_info) if agent_info else agent_name
        entities.append(AgentTokensSensor(coordinator, entry, agent_id, display_name, subentry_id))
        entities.append(AgentCostSensor(coordinator, entry, agent_id, display_name, subentry_id))

    async_add_entities(entities)


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


class _AgentUsageBase(CoordinatorEntity[AgentBridgeCoordinator], SensorEntity):
    """Common wiring for the per-agent usage sensors (CR-0009)."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AgentBridgeCoordinator,
        entry: ConfigEntry,
        agent_id: str,
        agent_name: str,
        subentry_id: str | None,
        kind: str,
    ) -> None:
        super().__init__(coordinator)
        self._agent_id = agent_id
        suffix = subentry_id or agent_id
        self._attr_unique_id = f"{entry.entry_id}_{suffix}_{kind}"
        # Attach to the agent's existing conversation/ai_task device (same tuple).
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{suffix}")},
            name=agent_name,
            manufacturer="Agent Bridge",
            model=agent_id,
            entry_type=DeviceEntryType.SERVICE,
        )

    def _usage(self) -> dict[str, Any]:
        """This agent's usage payload, or an empty dict."""
        data = self.coordinator.data
        if not data:
            return {}
        return data.get("usage", {}).get(self._agent_id, {}) or {}


class AgentTokensSensor(_AgentUsageBase):
    """Total tokens (in + out) this agent has used over the reported range."""

    _attr_translation_key = "agent_tokens"
    _attr_native_unit_of_measurement = "tokens"
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(self, coordinator, entry, agent_id, agent_name, subentry_id) -> None:
        super().__init__(coordinator, entry, agent_id, agent_name, subentry_id, "tokens")

    @property
    def name(self) -> str:
        return "Tokens used"

    @property
    def native_value(self) -> int | None:
        totals = self._usage().get("totals")
        if not isinstance(totals, dict):
            return None
        return int(totals.get("totalIn", 0)) + int(totals.get("totalOut", 0))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        usage = self._usage()
        if not usage:
            return {}
        totals = usage.get("totals", {}) if isinstance(usage.get("totals"), dict) else {}
        return {
            "input_tokens": totals.get("totalIn"),
            "output_tokens": totals.get("totalOut"),
            "turns": totals.get("turnCount"),
            "per_model": usage.get("perModel"),
            "range": usage.get("range"),
        }


class AgentCostSensor(_AgentUsageBase):
    """Estimated cost (GBP) this agent has incurred over the reported range."""

    _attr_translation_key = "agent_cost"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "GBP"
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(self, coordinator, entry, agent_id, agent_name, subentry_id) -> None:
        super().__init__(coordinator, entry, agent_id, agent_name, subentry_id, "cost")

    @property
    def name(self) -> str:
        return "Estimated cost"

    @property
    def native_value(self) -> float | None:
        # None when the bridge has no pricing configured (cost not estimable).
        cost = self._usage().get("estimatedTotalCostGBP")
        return float(cost) if isinstance(cost, (int, float)) else None


def _device_info(entry: ConfigEntry) -> dict:
    """Return device info for the single Agent Bridge device."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Agent Bridge",
        manufacturer="Engram Labs",
        model="Agent Bridge",
        entry_type=None,
    )
