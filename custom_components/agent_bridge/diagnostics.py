"""Diagnostics support for Agent Bridge (CR-0009).

Exposes the fleet-doctor verdict, per-agent usage/cost and the coordinator's
current view via HA's diagnostics download. The bridge token and caller id are
redacted; the agent list and usage carry no secrets.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_BRIDGE_TOKEN, CONF_CALLER_ID, DOMAIN

TO_REDACT = {CONF_BRIDGE_TOKEN, CONF_CALLER_ID}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    coordinator = data.get("coordinator")
    cdata = coordinator.data if coordinator and coordinator.data else {}

    agents = [
        {
            "id": a.get("id"),
            "name": a.get("name"),
            "healthy": a.get("healthy"),
            "health_state": a.get("health_state"),
            "crew": a.get("crew"),
            "deprecated": a.get("deprecated"),
        }
        for a in cdata.get("agents", [])
    ]

    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "entry_options": async_redact_data(dict(entry.options), TO_REDACT),
        "connected": cdata.get("connected"),
        "bridge_status": cdata.get("bridge_status"),
        "bridge_version": cdata.get("bridge_version"),
        "tool_surface": cdata.get("tool_surface"),
        "read_only_safe": cdata.get("read_only_safe"),
        "doctor": cdata.get("doctor", {}),
        "usage": cdata.get("usage", {}),
        "agents": agents,
    }
