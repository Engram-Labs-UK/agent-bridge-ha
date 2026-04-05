"""Conversation agent for Agent Bridge -- HA Assist integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import conversation
from homeassistant.components.conversation import AbstractConversationAgent
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import intent

from .client import BridgeClient, BridgeError
from .const import (
    CONF_CONTEXT_MAX_CHARS,
    CONF_CONTEXT_STRATEGY,
    CONF_DEBUG_LOGGING,
    CONF_DEFAULT_AGENT,
    CONF_ENABLE_TOOL_CALLS,
    CONF_VOICE_AGENT,
    DEFAULT_CONTEXT_MAX_CHARS,
    DEFAULT_CONTEXT_STRATEGY,
    DEFAULT_CONTINUATION_EXCLUSIONS,
    DEFAULT_CONTINUATION_PHRASES,
    DOMAIN,
    EVENT_MESSAGE_RECEIVED,
    MAX_TOOL_ITERATIONS,
)
from .exposure import async_get_exposed_entities, build_entity_context
from .helpers import extract_response_text, extract_tool_calls
from .tool_executor import execute_tool_call

_LOGGER = logging.getLogger(__name__)

# Error messages for voice-friendly output (no technical jargon)
ERROR_MESSAGES: dict[str, str] = {
    "AGENT_TIMEOUT": "The agent is taking too long to respond. Please try again.",
    "AGENT_UNREACHABLE": "The agent is currently unavailable.",
    "CIRCUIT_OPEN": "The agent is temporarily offline.",
    "NO_CAPABLE_AGENT": "No agent is available to handle this request.",
    "AUTH_ERROR": "There is an authentication problem with the bridge.",
    "RATE_LIMITED": "The agent is busy. Please try again shortly.",
    "CONNECTION_ERROR": "The bridge is offline.",
    "TIMEOUT": "The request timed out. Please try again.",
    "TOOL_LOOP": "The agent could not complete the request.",
}


def _resolve_area_name(
    hass: HomeAssistant,
    device_id: str | None,
) -> str | None:
    """Resolve the area name from a device ID."""
    if not device_id:
        return None

    device_reg = dr.async_get(hass)
    device_entry = device_reg.async_get(device_id)
    if not device_entry or not device_entry.area_id:
        return None

    area_reg = ar.async_get(hass)
    area = area_reg.async_get_area(device_entry.area_id)
    return area.name if area else None


def _build_system_prompt(
    *,
    area_name: str | None,
    entity_context: str,
    extra_system_prompt: str | None,
) -> str:
    """Build the three-layer system prompt: room + entities + extra."""
    parts: list[str] = []

    if area_name:
        parts.append(f"The user is in the {area_name}.")

    if entity_context:
        parts.append(entity_context)

    if extra_system_prompt:
        parts.append(extra_system_prompt)

    return "\n\n".join(parts)


def _detect_continuation(response_text: str) -> bool:
    """Detect whether the agent response is a follow-up question.

    Triggers when the final sentence ends with ? and contains a
    continuation phrase. Suppresses for exclusion phrases.
    """
    if not response_text:
        return False

    text = response_text.strip()
    if not text.endswith("?"):
        return False

    # Extract final sentence (split on . ! and take last non-empty)
    # Simple heuristic: find last sentence-ending punctuation before the final ?
    text_lower = text.lower()

    # Check exclusion phrases first
    for phrase in DEFAULT_CONTINUATION_EXCLUSIONS:
        if text_lower.endswith(phrase.lower()):
            return False

    # Check for continuation phrases
    return any(phrase.lower() in text_lower for phrase in DEFAULT_CONTINUATION_PHRASES)


async def _stream_chat(
    client: BridgeClient,
    messages: list[dict[str, Any]],
    *,
    agent: str | None = None,
    channel: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> str | None:
    """Attempt a streaming chat request, assembling deltas into a complete string.

    Returns the assembled text, or None if streaming produced no content.
    Raises on connection/auth errors (caller should fall back to non-streaming).
    """
    parts: list[str] = []
    async for delta in await client.chat_stream(
        messages, agent=agent, channel=channel, metadata=metadata
    ):
        parts.append(delta)
    return "".join(parts) if parts else None


class AgentBridgeConversationAgent(AbstractConversationAgent):
    """Conversation agent that routes through the Agent Bridge."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: BridgeClient,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.client = client

    @property
    def supported_languages(self) -> list[str] | str:
        """Return supported languages (delegate to AI model)."""
        return MATCH_ALL

    async def async_process(
        self,
        user_input: conversation.ConversationInput,
    ) -> conversation.ConversationResult:
        """Process a conversation turn."""
        options = self.entry.options

        # Resolve agent
        is_voice = user_input.device_id is not None
        if is_voice:
            agent_id = self.entry.data.get(
                CONF_VOICE_AGENT,
                self.entry.data.get(CONF_DEFAULT_AGENT),
            )
        else:
            agent_id = self.entry.data.get(CONF_DEFAULT_AGENT)

        # Resolve room context
        device_id = user_input.device_id
        # HA 2025+ may provide satellite_id separate from device_id
        satellite_id = getattr(user_input, "satellite_id", None)
        area_name = _resolve_area_name(self.hass, satellite_id or device_id)

        # Build entity context
        agent_entity_id = f"conversation.{DOMAIN}"
        exposed_ids = await async_get_exposed_entities(self.hass, agent_entity_id)
        entity_context = build_entity_context(
            self.hass,
            exposed_ids,
            max_chars=options.get(CONF_CONTEXT_MAX_CHARS, DEFAULT_CONTEXT_MAX_CHARS),
            strategy=options.get(CONF_CONTEXT_STRATEGY, DEFAULT_CONTEXT_STRATEGY),
        )

        # Build system prompt
        extra_system_prompt = getattr(user_input, "extra_system_prompt", None)
        system_prompt = _build_system_prompt(
            area_name=area_name,
            entity_context=entity_context,
            extra_system_prompt=extra_system_prompt,
        )

        # Get or create session
        from . import SessionManager

        data = self.hass.data[DOMAIN][self.entry.entry_id]
        session_manager: SessionManager = data["session_manager"]
        channel = session_manager.get_or_create(agent_id or "default")

        # Build metadata for voice requests
        metadata: dict[str, Any] | None = None
        if is_voice:
            metadata = {
                "source": "voice",
                "device_id": device_id,
                "area": area_name,
                "language": user_input.language,
            }
            if satellite_id:
                metadata["satellite_id"] = satellite_id

        # Debug logging
        if options.get(CONF_DEBUG_LOGGING, False):
            _LOGGER.info(
                "Voice routing: agent=%s session=%s area=%s device=%s satellite=%s",
                agent_id,
                channel,
                area_name,
                device_id,
                satellite_id,
            )

        # Build initial messages
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input.text},
        ]

        # Attempt streaming for first voice request, fall back to non-streaming
        enable_tools = options.get(CONF_ENABLE_TOOL_CALLS, True)
        exposed_set = set(exposed_ids)
        response_text: str | None = None
        response: dict[str, Any] = {}
        iterations = 0
        used_streaming = False

        try:
            # First request: try streaming for voice (no tool calls expected yet)
            if is_voice and not enable_tools:
                # Pure streaming (no tool loop) -- simplest path
                try:
                    streamed = await _stream_chat(
                        self.client,
                        messages,
                        agent=agent_id,
                        channel=channel,
                        metadata=metadata,
                    )
                    if streamed is not None:
                        response_text = streamed
                        used_streaming = True
                except (BridgeError, Exception):
                    _LOGGER.debug("Streaming failed, falling back to non-streaming")

            if not used_streaming:
                # Standard tool call loop (ADR-005: max 10 iterations)
                while iterations < MAX_TOOL_ITERATIONS:
                    iterations += 1

                    response = await self.client.chat(
                        messages,
                        agent=agent_id,
                        channel=channel,
                        metadata=metadata,
                    )

                    tool_calls = extract_tool_calls(response) if enable_tools else []
                    content = extract_response_text(response)

                    if not tool_calls:
                        response_text = content
                        break

                    # Execute tool calls (ADR-005: tools first, preserve content)
                    assistant_message: dict[str, Any] = {
                        "role": "assistant",
                        "content": content,
                        "tool_calls": tool_calls,
                    }
                    messages.append(assistant_message)

                    for tc in tool_calls:
                        result = await execute_tool_call(self.hass, tc, exposed_set)
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc.get("id", ""),
                                "content": _json_str(result),
                            }
                        )

                    # Metadata only needed on first request
                    metadata = None

                else:
                    # Loop cap exceeded
                    response_text = ERROR_MESSAGES["TOOL_LOOP"]

        except BridgeError as err:
            response_text = ERROR_MESSAGES.get(err.code, str(err))

        # Save session after conversation
        await session_manager.async_save()

        # Fire event
        agent_response = response_text or ""
        model = ""
        if isinstance(response, dict):
            model = response.get("model", "")
            agent_id = response.get("agent", agent_id)

        self.hass.bus.async_fire(
            EVENT_MESSAGE_RECEIVED,
            {
                "agent_id": agent_id,
                "model": model,
                "content_preview": agent_response[:200],
            },
        )

        # Build result
        intent_response = intent.IntentResponse(language=user_input.language)
        intent_response.async_set_speech(agent_response)

        continue_conversation = _detect_continuation(agent_response)

        return conversation.ConversationResult(
            response=intent_response,
            conversation_id=channel,
            continue_conversation=continue_conversation,
        )


def _json_str(data: Any) -> str:
    """Convert data to JSON string for tool results."""
    import json

    return json.dumps(data, default=str)


class PerAgentConversationAgent(AgentBridgeConversationAgent):
    """Conversation agent for a specific bridge agent (per-agent mode)."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: BridgeClient,
        agent_id: str,
        agent_name: str,
    ) -> None:
        super().__init__(hass, entry, client)
        self._fixed_agent_id = agent_id
        self._agent_name = agent_name

    async def async_process(
        self,
        user_input: conversation.ConversationInput,
    ) -> conversation.ConversationResult:
        """Process a conversation turn routed to this specific agent."""
        # Override agent resolution -- always use this agent
        # Store original method reference to restore later
        original_data = self.entry.data

        # Temporarily override default agent so the parent class routes correctly
        patched_data = dict(original_data)
        patched_data[CONF_DEFAULT_AGENT] = self._fixed_agent_id
        patched_data[CONF_VOICE_AGENT] = self._fixed_agent_id

        # Use a simple approach: call parent with agent forced
        # The parent reads CONF_DEFAULT_AGENT / CONF_VOICE_AGENT from entry.data
        # We can't safely patch entry.data, so override inline instead

        return await self._process_with_agent(user_input, self._fixed_agent_id)

    async def _process_with_agent(
        self,
        user_input: conversation.ConversationInput,
        agent_id: str,
    ) -> conversation.ConversationResult:
        """Process with a specific forced agent ID."""
        options = self.entry.options

        # Resolve room context
        device_id = user_input.device_id
        satellite_id = getattr(user_input, "satellite_id", None)
        area_name = _resolve_area_name(self.hass, satellite_id or device_id)

        # Build entity context
        agent_entity_id = f"conversation.{DOMAIN}_{agent_id}"
        exposed_ids = await async_get_exposed_entities(self.hass, agent_entity_id)
        entity_context = build_entity_context(
            self.hass,
            exposed_ids,
            max_chars=options.get(CONF_CONTEXT_MAX_CHARS, DEFAULT_CONTEXT_MAX_CHARS),
            strategy=options.get(CONF_CONTEXT_STRATEGY, DEFAULT_CONTEXT_STRATEGY),
        )

        extra_system_prompt = getattr(user_input, "extra_system_prompt", None)
        system_prompt = _build_system_prompt(
            area_name=area_name,
            entity_context=entity_context,
            extra_system_prompt=extra_system_prompt,
        )

        from . import SessionManager

        data = self.hass.data[DOMAIN][self.entry.entry_id]
        session_manager: SessionManager = data["session_manager"]
        channel = session_manager.get_or_create(agent_id)

        is_voice = device_id is not None
        metadata: dict[str, Any] | None = None
        if is_voice:
            metadata = {
                "source": "voice",
                "device_id": device_id,
                "area": area_name,
                "language": user_input.language,
            }
            if satellite_id:
                metadata["satellite_id"] = satellite_id

        if options.get(CONF_DEBUG_LOGGING, False):
            _LOGGER.info(
                "Per-agent routing: agent=%s session=%s area=%s",
                agent_id,
                channel,
                area_name,
            )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input.text},
        ]

        enable_tools = options.get(CONF_ENABLE_TOOL_CALLS, True)
        exposed_set = set(exposed_ids)
        response_text: str | None = None
        response: dict[str, Any] = {}
        iterations = 0

        try:
            while iterations < MAX_TOOL_ITERATIONS:
                iterations += 1
                response = await self.client.chat(
                    messages, agent=agent_id, channel=channel, metadata=metadata
                )
                tool_calls = extract_tool_calls(response) if enable_tools else []
                content = extract_response_text(response)

                if not tool_calls:
                    response_text = content
                    break

                assistant_message: dict[str, Any] = {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": tool_calls,
                }
                messages.append(assistant_message)
                for tc in tool_calls:
                    result = await execute_tool_call(self.hass, tc, exposed_set)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.get("id", ""),
                            "content": _json_str(result),
                        }
                    )
                metadata = None
            else:
                response_text = ERROR_MESSAGES["TOOL_LOOP"]
        except BridgeError as err:
            response_text = ERROR_MESSAGES.get(err.code, str(err))

        await session_manager.async_save()

        agent_response = response_text or ""
        model = response.get("model", "") if isinstance(response, dict) else ""

        self.hass.bus.async_fire(
            EVENT_MESSAGE_RECEIVED,
            {
                "agent_id": agent_id,
                "model": model,
                "content_preview": agent_response[:200],
            },
        )

        intent_response = intent.IntentResponse(language=user_input.language)
        intent_response.async_set_speech(agent_response)

        return conversation.ConversationResult(
            response=intent_response,
            conversation_id=channel,
            continue_conversation=_detect_continuation(agent_response),
        )


async def async_setup_conversation_agent(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Register the primary conversation agent with HA."""
    data = hass.data[DOMAIN][entry.entry_id]
    client: BridgeClient = data["client"]

    agent = AgentBridgeConversationAgent(hass, entry, client)
    conversation.async_set_agent(hass, entry, agent)
    data["conversation_agent"] = agent
    data["per_agent_entities"] = {}


async def async_setup_per_agent_conversations(
    hass: HomeAssistant,
    entry: ConfigEntry,
    agents: list[dict[str, Any]],
) -> None:
    """Create per-agent conversation agent entities for discovered agents."""
    data = hass.data[DOMAIN][entry.entry_id]
    client: BridgeClient = data["client"]
    per_agent: dict[str, PerAgentConversationAgent] = data.get("per_agent_entities", {})

    for agent_info in agents:
        agent_id = agent_info.get("id", "")
        capabilities = agent_info.get("capabilities", {})

        # Only create for chat-capable agents
        if not capabilities.get("chat", False):
            continue

        if agent_id not in per_agent:
            agent_name = agent_info.get("name", agent_id)
            per_agent_conv = PerAgentConversationAgent(hass, entry, client, agent_id, agent_name)
            # Register with HA using a unique agent ID
            conversation.async_set_agent(
                hass, entry, per_agent_conv, agent_id=f"{DOMAIN}_{agent_id}"
            )
            per_agent[agent_id] = per_agent_conv
            _LOGGER.info("Registered per-agent conversation: %s", agent_id)

    data["per_agent_entities"] = per_agent


async def async_remove_per_agent_conversation(
    hass: HomeAssistant,
    entry: ConfigEntry,
    agent_id: str,
) -> None:
    """Remove a per-agent conversation agent."""
    data = hass.data[DOMAIN][entry.entry_id]
    per_agent: dict[str, PerAgentConversationAgent] = data.get("per_agent_entities", {})

    if agent_id in per_agent:
        conversation.async_unset_agent(hass, entry, agent_id=f"{DOMAIN}_{agent_id}")
        del per_agent[agent_id]
        _LOGGER.info("Unregistered per-agent conversation: %s", agent_id)


async def async_unload_conversation_agent(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Unregister all conversation agents from HA."""
    data = hass.data[DOMAIN].get(entry.entry_id, {})

    # Unregister per-agent conversations
    per_agent: dict[str, PerAgentConversationAgent] = data.get("per_agent_entities", {})
    for agent_id in list(per_agent.keys()):
        conversation.async_unset_agent(hass, entry, agent_id=f"{DOMAIN}_{agent_id}")
    per_agent.clear()

    # Unregister primary
    conversation.async_unset_agent(hass, entry)
