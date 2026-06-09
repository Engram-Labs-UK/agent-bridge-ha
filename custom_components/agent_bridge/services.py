"""HA services for Agent Bridge -- send_message, invoke_tool."""

from __future__ import annotations

import base64
import logging
from typing import Any

import voluptuous as vol
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .client import BridgeClient, BridgeError
from .const import CONF_DEFAULT_AGENT, DOMAIN
from .coordinator import AgentBridgeCoordinator
from .helpers import extract_response_text

_LOGGER = logging.getLogger(__name__)

SERVICE_SEND_MESSAGE = "send_message"
SERVICE_INVOKE_TOOL = "invoke_tool"
SERVICE_BROADCAST = "broadcast"
SERVICE_ASK_WITH_IMAGE = "ask_with_image"
SERVICE_ANNOUNCE = "announce"
SERVICE_MEMORY_RECORD = "memory_record"
SERVICE_MEMORY_RECALL = "memory_recall"

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

ASK_WITH_IMAGE_SCHEMA = vol.Schema(
    {
        vol.Required("message"): cv.string,
        vol.Required("camera_entity_id"): cv.entity_id,
        vol.Optional("agent_id"): cv.string,
        vol.Optional("session_id"): cv.string,
    }
)

ANNOUNCE_SCHEMA = vol.Schema(
    {
        vol.Required("message"): cv.string,
        vol.Required("target"): cv.entity_id,
        vol.Optional("priority", default="normal"): vol.In(["low", "normal", "critical"]),
    }
)

MEMORY_RECORD_SCHEMA = vol.Schema(
    {
        vol.Required("content"): cv.string,
        vol.Optional("agent_id"): cv.string,
        vol.Optional("tags"): vol.All(cv.ensure_list, [cv.string]),
    }
)

MEMORY_RECALL_SCHEMA = vol.Schema(
    {
        vol.Optional("query"): cv.string,
        vol.Optional("agent_id"): cv.string,
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


def _default_agent(hass: HomeAssistant) -> str | None:
    """The configured default agent id, used when a service omits ``agent_id``."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if entries:
        return entries[0].data.get(CONF_DEFAULT_AGENT)
    return None


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


async def async_handle_ask_with_image(call: ServiceCall) -> ServiceResponse:
    """Handle ask_with_image: snapshot a camera and send it to an agent (US0035)."""
    # Imported lazily so the camera component is only required when this is used.
    from homeassistant.components.camera import async_get_image

    hass = call.hass
    data = _get_entry_data(hass)
    client: BridgeClient = data["client"]
    coordinator: AgentBridgeCoordinator = data["coordinator"]

    message = call.data["message"]
    camera_entity_id = call.data["camera_entity_id"]
    agent_id = call.data.get("agent_id")
    session_id = call.data.get("session_id")

    if agent_id:
        _validate_agent_id(coordinator, agent_id)

    try:
        image = await async_get_image(hass, camera_entity_id, timeout=10)
    except HomeAssistantError as err:
        return {"response": "", "error": f"Could not capture {camera_entity_id}: {err}"}

    b64 = base64.b64encode(image.content).decode("ascii")
    attachments = [
        {
            "id": f"ha-camera-{camera_entity_id}",
            "mime_type": image.content_type or "image/jpeg",
            "base64": b64,
            "source": {"bot_id": "homeassistant"},
        }
    ]
    messages = [{"role": "user", "content": message}]

    try:
        response = await client.chat(
            messages,
            agent=agent_id,
            channel=session_id,
            attachments=attachments,
        )
        return {
            "response": extract_response_text(response) or "",
            "agent_id": response.get("agent", agent_id or ""),
            "model": response.get("model", ""),
        }
    except BridgeError as err:
        return {"response": "", "error": str(err)}


async def async_handle_announce(call: ServiceCall) -> ServiceResponse:
    """Proactively speak a message on a satellite (US0037).

    With Option A the agent actuates HA via its own ``/api/mcp`` mount, so it can
    call this service directly to push speech -- no separate HA-side listener is
    needed. Adds Cora's asks: a specific ``assist_satellite`` target, priority,
    and skipping a satellite that is unavailable (don't announce into the void)
    unless the message is ``critical``.
    """
    hass = call.hass
    message = call.data["message"]
    target = call.data["target"]
    priority = call.data.get("priority", "normal")

    state = hass.states.get(target)
    available = state is not None and state.state not in ("unavailable", "unknown")
    if not available and priority != "critical":
        return {
            "announced": False,
            "target": target,
            "reason": f"{target} is unavailable; skipped (priority={priority})",
        }

    try:
        await hass.services.async_call(
            "assist_satellite",
            "announce",
            {"entity_id": target, "message": message},
            blocking=True,
        )
    except (HomeAssistantError, vol.Invalid) as err:
        return {"announced": False, "target": target, "error": str(err)}
    return {"announced": True, "target": target, "priority": priority}


async def async_handle_memory_record(call: ServiceCall) -> ServiceResponse:
    """Record a memory item for an agent (CR-0010)."""
    hass = call.hass
    data = _get_entry_data(hass)
    client: BridgeClient = data["client"]
    coordinator: AgentBridgeCoordinator = data["coordinator"]

    explicit = call.data.get("agent_id")
    if explicit:
        _validate_agent_id(coordinator, explicit)
    agent_id = explicit or _default_agent(hass)
    if not agent_id:
        return {"recorded": False, "error": "no agent specified and no default agent configured"}

    try:
        await client.memory_record(agent_id, call.data["content"], tags=call.data.get("tags"))
        return {"recorded": True, "agent_id": agent_id}
    except BridgeError as err:
        return {"recorded": False, "agent_id": agent_id, "error": str(err)}


async def async_handle_memory_recall(call: ServiceCall) -> ServiceResponse:
    """Recall an agent's memory items (CR-0010)."""
    hass = call.hass
    data = _get_entry_data(hass)
    client: BridgeClient = data["client"]
    coordinator: AgentBridgeCoordinator = data["coordinator"]

    explicit = call.data.get("agent_id")
    if explicit:
        _validate_agent_id(coordinator, explicit)
    agent_id = explicit or _default_agent(hass)
    if not agent_id:
        return {"items": [], "error": "no agent specified and no default agent configured"}

    try:
        response = await client.memory_recall(agent_id, query=call.data.get("query"))
        items = response.get("items") if isinstance(response, dict) else None
        return {"items": items if isinstance(items, list) else [], "agent_id": agent_id}
    except BridgeError as err:
        return {"items": [], "agent_id": agent_id, "error": str(err)}


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

    hass.services.async_register(
        DOMAIN,
        SERVICE_ASK_WITH_IMAGE,
        async_handle_ask_with_image,
        schema=ASK_WITH_IMAGE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ANNOUNCE,
        async_handle_announce,
        schema=ANNOUNCE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_MEMORY_RECORD,
        async_handle_memory_record,
        schema=MEMORY_RECORD_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_MEMORY_RECALL,
        async_handle_memory_recall,
        schema=MEMORY_RECALL_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unregister Agent Bridge services."""
    hass.services.async_remove(DOMAIN, SERVICE_SEND_MESSAGE)
    hass.services.async_remove(DOMAIN, SERVICE_INVOKE_TOOL)
    hass.services.async_remove(DOMAIN, SERVICE_BROADCAST)
    hass.services.async_remove(DOMAIN, SERVICE_ASK_WITH_IMAGE)
    hass.services.async_remove(DOMAIN, SERVICE_ANNOUNCE)
    hass.services.async_remove(DOMAIN, SERVICE_MEMORY_RECORD)
    hass.services.async_remove(DOMAIN, SERVICE_MEMORY_RECALL)
