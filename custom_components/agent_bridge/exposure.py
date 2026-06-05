"""Entity exposure -- format HA entity state for AI context."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import (
    area_registry as ar,
)
from homeassistant.helpers import (
    device_registry as dr,
)
from homeassistant.helpers import (
    entity_registry as er,
)

from .const import MAX_ENTITIES

_LOGGER = logging.getLogger(__name__)

# Attributes worth including in entity context for AI consumption
RELEVANT_ATTRIBUTES = frozenset(
    {
        "brightness",
        "color_temp",
        "temperature",
        "current_temperature",
        "target_temperature",
        "volume_level",
        "battery_level",
        "media_title",
        "media_artist",
        "hvac_mode",
        "fan_mode",
        "preset_mode",
        "is_locked",
        "position",
    }
)


def _format_entity(
    state: State,
    area_name: str | None,
    relevant_attrs: dict[str, Any],
) -> str:
    """Format a single entity for AI context.

    Format: Friendly Name (entity_id): state [area: Kitchen] [brightness: 75]
    """
    parts = [f"{state.name} ({state.entity_id}): {state.state}"]

    if area_name:
        parts.append(f"[area: {area_name}]")

    for attr_name, attr_value in relevant_attrs.items():
        parts.append(f"[{attr_name}: {attr_value}]")

    return " ".join(parts)


def _get_entity_area(
    entity_entry: er.RegistryEntry | None,
    device_entry: dr.DeviceEntry | None,
    area_reg: ar.AreaRegistry,
) -> str | None:
    """Resolve the area name for an entity (entity area > device area)."""
    # Entity-level area takes priority
    if entity_entry and entity_entry.area_id:
        area = area_reg.async_get_area(entity_entry.area_id)
        if area:
            return area.name

    # Fall back to device area
    if device_entry and device_entry.area_id:
        area = area_reg.async_get_area(device_entry.area_id)
        if area:
            return area.name

    return None


def _get_relevant_attributes(state: State) -> dict[str, Any]:
    """Extract relevant attributes from an entity state."""
    attrs = {}
    for attr_name in RELEVANT_ATTRIBUTES:
        if attr_name in state.attributes:
            value = state.attributes[attr_name]
            if value is not None:
                attrs[attr_name] = value
    return attrs


async def async_get_exposed_entities(
    hass: HomeAssistant,
    agent_id: str,
) -> list[str]:
    """Get the list of entity IDs exposed to this conversation agent."""
    exposed: list[str] = []
    entity_reg = er.async_get(hass)

    for state in hass.states.async_all():
        entity_entry = entity_reg.async_get(state.entity_id)
        # Use HA's conversation expose check
        if entity_entry and _is_entity_exposed(hass, agent_id, state.entity_id):
            exposed.append(state.entity_id)

    return exposed


def _is_entity_exposed(
    hass: HomeAssistant,
    agent_id: str,
    entity_id: str,
) -> bool:
    """Check whether an entity is exposed to the conversation agent."""
    try:
        from homeassistant.components.homeassistant.exposed_entities import (
            async_should_expose,
        )

        return async_should_expose(hass, "conversation", entity_id)
    except ImportError:
        # US0027/AC4 + CR-0002/G4: fail CLOSED. If HA's exposure helper cannot be
        # imported we must NOT expose every entity (the previous fail-open bug);
        # skip the entity. Deliberate, logged fallback so a genuine HA-API move is
        # visible rather than silently hiding (or over-exposing) the home.
        _LOGGER.warning(
            "HA exposure helper unavailable; failing CLOSED for %s "
            "(entity skipped). This may indicate an HA version/API change.",
            entity_id,
        )
        return False


def build_entity_context(
    hass: HomeAssistant,
    exposed_entity_ids: list[str],
    *,
    max_chars: int = 200000,
    strategy: str = "truncate",
) -> str:
    """Build the entity context string for the AI system prompt.

    Args:
        hass: Home Assistant instance.
        exposed_entity_ids: Entity IDs to include (pre-filtered by exposure).
        max_chars: Maximum character length for the context.
        strategy: "truncate" to cut at limit, "clear" to return empty if exceeded.
    """
    entity_reg = er.async_get(hass)
    device_reg = dr.async_get(hass)
    area_reg = ar.async_get(hass)

    lines: list[str] = []
    count = 0

    for entity_id in exposed_entity_ids:
        if count >= MAX_ENTITIES:
            break

        state = hass.states.get(entity_id)
        if state is None or state.state in ("unavailable", "unknown"):
            continue

        entity_entry = entity_reg.async_get(entity_id)
        device_entry = None
        if entity_entry and entity_entry.device_id:
            device_entry = device_reg.async_get(entity_entry.device_id)

        area_name = _get_entity_area(entity_entry, device_entry, area_reg)
        relevant_attrs = _get_relevant_attributes(state)

        line = _format_entity(state, area_name, relevant_attrs)
        lines.append(line)
        count += 1

    context = "\n".join(lines)

    if len(context) > max_chars:
        if strategy == "clear":
            return ""
        # Truncate at last complete line within limit
        truncated_lines: list[str] = []
        total = 0
        for line in lines:
            if total + len(line) + 1 > max_chars:
                break
            truncated_lines.append(line)
            total += len(line) + 1
        context = "\n".join(truncated_lines)

    return context


def build_recent_changes(
    hass: HomeAssistant,
    exposed_entity_ids: list[str],
    *,
    now: datetime,
    window_s: int = 1800,
    max_items: int = 10,
    max_chars: int = 800,
) -> str:
    """List exposed entities that changed within the last ``window_s`` seconds.

    A diagnostic grounding hint (US0034): "why is it so hot?" is answerable when
    the agent can see the thermostat changed recently. Shows the current value +
    rough age (old values would need the recorder -- out of scope). Bounded to
    ``max_items`` and ``max_chars`` (the source block is not otherwise budgeted),
    most-recent first; returns "" when nothing changed recently.
    """
    changed: list[tuple[float, State]] = []
    for entity_id in exposed_entity_ids:
        state = hass.states.get(entity_id)
        if state is None:
            continue
        age = (now - state.last_changed).total_seconds()
        if 0 <= age <= window_s:
            changed.append((age, state))

    changed.sort(key=lambda item: item[0])
    lines: list[str] = []
    total = 0
    for age, state in changed[:max_items]:
        mins = int(age // 60)
        ago = f"{mins}m ago" if mins else "just now"
        line = f"{state.name} ({state.entity_id}): {state.state} (changed {ago})"
        if total + len(line) + 1 > max_chars:
            break
        lines.append(line)
        total += len(line) + 1
    return "\n".join(lines)
