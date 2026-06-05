"""HA services for Agent Bridge -- send_message, invoke_tool."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.helpers import config_validation as cv

from .client import BridgeClient, BridgeError
from .const import DOMAIN
from .coordinator import AgentBridgeCoordinator
from .helpers import extract_response_text

_LOGGER = logging.getLogger(__name__)

SERVICE_SEND_MESSAGE = "send_message"
SERVICE_INVOKE_TOOL = "invoke_tool"
SERVICE_BROADCAST = "broadcast"

SEND_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required("message"): cv.string,
        vol.Optional("agent_id"): cv.string,
        vol.Optional("session_id"): cv.string,
    }
)

INVOKE_TOOL_SCHEMA = vol.Schema(
    {
        vol.Required("agent_id"): cv.string,
        vol.Required("tool_name"): cv.string,
        vol.Optional("args"): dict,
    }
)

BROADCAST_SCHEMA = vol.Schema(
    {
        vol.Required("message"): cv.string,
        vol.Optional("tags"): vol.All(cv.ensure_list, [cv.string]),
    }
)


def _get_entry_data(hass: HomeAssistant) -> dict[str, Any]:
    """Get the first config entry's runtime data."""
    entries = hass.data.get(DOMAIN, {})
    if not entries:
        raise ValueError("Agent Bridge is not configured")
    entry_id = next(iter(entries))
    return entries[entry_id]


def _validate_agent_id(coordinator: AgentBridgeCoordinator, agent_id: str) -> None:
    """Validate that agent_id exists in the coordinator's cached agent list."""
    if not coordinator.data:
        raise ValueError("Bridge data not available")
    known_ids = {a["id"] for a in coordinator.data["agents"]}
    if agent_id not in known_ids:
        raise ValueError(f"Unknown agent: {agent_id}")


async def async_handle_send_message(call: ServiceCall) -> ServiceResponse:
    """Handle the send_message service call."""
    hass = call.hass
    data = _get_entry_data(hass)
    client: BridgeClient = data["client"]
    coordinator: AgentBridgeCoordinator = data["coordinator"]

    message = call.data["message"]
    agent_id = call.data.get("agent_id")
    session_id = call.data.get("session_id")

    if agent_id:
        _validate_agent_id(coordinator, agent_id)

    messages = [{"role": "user", "content": message}]

    try:
        # The service passes the caller-supplied session_id straight through as the
        # bridge channel: scripted/automation callers want explicit, stable session
        # control. This is intentionally distinct from the conversation entity's
        # idle-windowed channel key (US0032), which auto-scopes per satellite/speaker.
        response = await client.chat(
            messages,
            agent=agent_id,
            channel=session_id,
        )
        response_text = extract_response_text(response) or ""
        return {
            "response": response_text,
            "agent_id": response.get("agent", agent_id or ""),
            "model": response.get("model", ""),
        }
    except BridgeError as err:
        return {
            "response": "",
            "error": str(err),
        }


async def async_handle_invoke_tool(call: ServiceCall) -> ServiceResponse:
    """Handle the invoke_tool service call."""
    hass = call.hass
    data = _get_entry_data(hass)
    client: BridgeClient = data["client"]
    coordinator: AgentBridgeCoordinator = data["coordinator"]

    agent_id = call.data["agent_id"]
    tool_name = call.data["tool_name"]
    args = call.data.get("args", {})

    _validate_agent_id(coordinator, agent_id)

    try:
        response = await client.invoke_tool(agent_id, tool_name, args)
        return {
            "response": response,
            "agent_id": agent_id,
        }
    except BridgeError as err:
        return {
            "response": None,
            "error": str(err),
        }


def _normalise_broadcast_responses(raw: Any) -> list[dict[str, Any]]:
    """Normalise the v4.36 broadcast ``responses`` object into a list.

    The bridge returns ``responses`` as an OBJECT keyed by agentId
    (e.g. ``{"cora": {...}, "eve": {...}}``); iterate by key and fold the key
    in as ``agent_id`` so HA consumers get a stable list shape. Defensively
    accepts the legacy list form too (US0022/G5).
    """
    if isinstance(raw, dict):
        normalised: list[dict[str, Any]] = []
        for agent_id, value in raw.items():
            entry = dict(value) if isinstance(value, dict) else {"response": value}
            entry.setdefault("agent_id", agent_id)
            normalised.append(entry)
        return normalised
    if isinstance(raw, list):
        return [r for r in raw if isinstance(r, dict)]
    return []


async def async_handle_broadcast(call: ServiceCall) -> ServiceResponse:
    """Handle the broadcast service call."""
    hass = call.hass
    data = _get_entry_data(hass)
    client: BridgeClient = data["client"]

    message = call.data["message"]
    tags = call.data.get("tags")

    try:
        response = await client.broadcast(message, tags=tags)
        return {
            "responses": _normalise_broadcast_responses(response.get("responses")),
        }
    except BridgeError as err:
        return {
            "responses": [],
            "error": str(err),
        }


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register Agent Bridge services."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        async_handle_send_message,
        schema=SEND_MESSAGE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_INVOKE_TOOL,
        async_handle_invoke_tool,
        schema=INVOKE_TOOL_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_BROADCAST,
        async_handle_broadcast,
        schema=BROADCAST_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unregister Agent Bridge services."""
    hass.services.async_remove(DOMAIN, SERVICE_SEND_MESSAGE)
    hass.services.async_remove(DOMAIN, SERVICE_INVOKE_TOOL)
    hass.services.async_remove(DOMAIN, SERVICE_BROADCAST)
