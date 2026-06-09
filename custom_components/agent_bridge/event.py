"""Event platform for Agent Bridge."""

from __future__ import annotations

from typing import ClassVar

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, EVENT_MESSAGE_RECEIVED


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Agent Bridge event entities."""
    async_add_entities([MessageReceivedEvent(entry)])


class MessageReceivedEvent(EventEntity):
    """Event entity that fires when an agent responds."""

    _attr_has_entity_name = True
    _attr_event_types: ClassVar[list[str]] = ["message_received"]

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
