"""Event platform for Agent Bridge."""

from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, EVENT_MESSAGE_RECEIVED, EVENT_TOOL_INVOKED


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Agent Bridge event entities."""
    async_add_entities(
        [
            MessageReceivedEvent(entry),
            ToolInvokedEvent(entry),
        ]
    )


class MessageReceivedEvent(EventEntity):
    """Event entity that fires when an agent responds."""

    _attr_has_entity_name = True
    _attr_event_types = ["message_received"]

    def __init__(self, entry: ConfigEntry) -> None:
        self._attr_unique_id = f"{entry.entry_id}_message_received"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Agent Bridge",
            manufacturer="Engram Labs",
            model="Agent Bridge",
        )
        self._entry = entry

    @property
    def name(self) -> str:
        """Return entity name."""
        return "Message Received"

    async def async_added_to_hass(self) -> None:
        """Register event listener when entity is added."""
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_MESSAGE_RECEIVED, self._handle_event)
        )

    @callback
    def _handle_event(self, event) -> None:
        """Handle the bus event and trigger the entity event."""
        self._trigger_event(
            "message_received",
            {
                "agent_id": event.data.get("agent_id", ""),
                "model": event.data.get("model", ""),
                "content_preview": event.data.get("content_preview", ""),
            },
        )
        self.async_write_ha_state()


class ToolInvokedEvent(EventEntity):
    """Event entity that fires when a tool is invoked."""

    _attr_has_entity_name = True
    _attr_event_types = ["tool_invoked_ok", "tool_invoked_error"]

    def __init__(self, entry: ConfigEntry) -> None:
        self._attr_unique_id = f"{entry.entry_id}_tool_invoked"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Agent Bridge",
            manufacturer="Engram Labs",
            model="Agent Bridge",
        )
        self._entry = entry

    @property
    def name(self) -> str:
        """Return entity name."""
        return "Tool Invoked"

    async def async_added_to_hass(self) -> None:
        """Register event listener when entity is added."""
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_TOOL_INVOKED, self._handle_event)
        )

    @callback
    def _handle_event(self, event) -> None:
        """Handle the bus event and trigger the entity event."""
        status = event.data.get("status", "error")
        event_type = f"tool_invoked_{status}"

        self._trigger_event(
            event_type,
            {
                "agent_id": event.data.get("agent_id", ""),
                "tool_name": event.data.get("tool_name", ""),
                "duration_ms": event.data.get("duration_ms", 0),
                "status": status,
            },
        )
        self.async_write_ha_state()
