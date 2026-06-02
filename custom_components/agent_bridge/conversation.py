"""Conversation entity for Agent Bridge -- HA Assist integration.

US0025/US0026 (EP0007): one ``ConversationEntity`` per bridge agent, created via
config subentries (HA 2025.2+ pattern, mirroring the OpenAI/Google integrations),
using ``_async_handle_message`` + ``ChatLog`` instead of the retired legacy
``AbstractConversationAgent`` direct-registration path and the bespoke
``SessionManager`` history.

Per the refined Option A (US0021 spike), this entity is the Assist front-end: it
forwards the utterance + an entity grounding hint as **free text** to the selected
bridge agent and returns the reply. The agent actuates HA itself via its own
``/api/mcp`` mount (US0027/US0031) -- this entity does not run an HA tool loop.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import conversation
from homeassistant.components.conversation import (
    AssistantContent,
    ChatLog,
    ConversationEntity,
    UserContent,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import intent
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .client import BridgeClient, BridgeError
from .const import (
    CONF_AGENT_ID,
    CONF_CONTEXT_MAX_CHARS,
    CONF_CONTEXT_STRATEGY,
    CONF_DEBUG_LOGGING,
    CONF_DEFAULT_AGENT,
    CONF_PROMPT,
    DEFAULT_CONTEXT_MAX_CHARS,
    DEFAULT_CONTEXT_STRATEGY,
    DEFAULT_CONTINUATION_EXCLUSIONS,
    DEFAULT_CONTINUATION_PHRASES,
    DEFAULT_PROMPT,
    DENY_CONFIRM_DOMAINS,
    DOMAIN,
    EVENT_ACTUATION_AUDIT,
    EVENT_MESSAGE_RECEIVED,
    SUBENTRY_TYPE_CONVERSATION,
)
from .exposure import async_get_exposed_entities, build_entity_context
from .helpers import extract_response_text

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
    instructions: str | None = None,
) -> str:
    """Build the layered system prompt: instructions + room + entities + extra.

    ``instructions`` is the operator-editable origin/role layer (CR-0003) telling
    the agent the turn is from Home Assistant and to actuate via its HA tools. The
    entity context is a **grounding hint** (names/areas/aliases), not state
    authority -- the agent reads live HA state itself before acting (US0027).
    """
    parts: list[str] = []

    if instructions:
        parts.append(instructions)

    if area_name:
        parts.append(f"The user is in the {area_name}.")

    if entity_context:
        parts.append(entity_context)

    if extra_system_prompt:
        parts.append(extra_system_prompt)

    return "\n\n".join(parts)


def _risky_domains_present(exposed_entity_ids: list[str]) -> set[str]:
    """Return the deny/confirm domains present among the exposed entities (US0027)."""
    present: set[str] = set()
    for entity_id in exposed_entity_ids:
        domain = entity_id.split(".", 1)[0]
        if domain in DENY_CONFIRM_DOMAINS:
            present.add(domain)
    return present


def _safety_caution(risky_domains: set[str]) -> str:
    """Build the deny/confirm caution folded into the grounding prompt (US0027).

    The agent actuates HA itself; this instructs it to confirm with the user
    before acting on safety-relevant domains (locks, alarms, heating, external
    doors) and to read live state back to confirm the result.
    """
    if not risky_domains:
        return ""
    domains = ", ".join(sorted(risky_domains))
    return (
        "SAFETY: before actuating safety-relevant devices "
        f"({domains}), confirm with the user first, then read the device's live "
        "state back to verify the change. Never silently actuate locks, alarms, "
        "heating, or external doors."
    )


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


def _messages_from_chat_log(chat_log: ChatLog) -> list[dict[str, Any]]:
    """Convert ``ChatLog`` history into bridge chat messages (US0026/AC2).

    History is sourced from ``ChatLog`` (not the retired ``SessionManager``).
    System content is rebuilt per-turn, so it is skipped here.
    """
    messages: list[dict[str, Any]] = []
    for content in chat_log.content:
        role = getattr(content, "role", None)
        text = getattr(content, "content", None)
        if role == "system" or not text:
            continue
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": text})
    return messages


def _agents_from_entry(
    entry: ConfigEntry,
) -> list[tuple[str, str, str | None, str]]:
    """Resolve (agent_id, agent_name, subentry_id, prompt) tuples to host entities.

    Prefers config subentries of type ``conversation`` (US0025), carrying each
    agent's editable instructions (CR-0003). Falls back to the single configured
    default agent (with the default prompt) for installs that predate subentries --
    migration is offered, not forced.
    """
    agents: list[tuple[str, str, str | None, str]] = []
    for subentry_id, subentry in entry.subentries.items():
        if getattr(subentry, "subentry_type", None) != SUBENTRY_TYPE_CONVERSATION:
            continue
        agent_id = subentry.data.get(CONF_AGENT_ID)
        if not agent_id:
            continue
        agent_name = getattr(subentry, "title", None) or agent_id
        prompt = subentry.data.get(CONF_PROMPT, DEFAULT_PROMPT)
        agents.append((agent_id, agent_name, subentry_id, prompt))

    if not agents:
        default_agent = entry.data.get(CONF_DEFAULT_AGENT)
        if default_agent:
            agents.append((default_agent, default_agent, None, DEFAULT_PROMPT))

    return agents


def _is_voice_capable(agent_info: dict[str, Any] | None) -> bool:
    """Gate voice-entity creation on the v4.36 taxonomy (US0028/AC3 + CR-0003).

    Only full **agents** (``agentClass: 'agent'`` with a real identity) become
    voice entities -- not orchestrators, chatbots (no tools), workerbots (no chat),
    or bare model passthroughs (``identitySubstrate: 'none'``). Agents with no
    discovery record / no taxonomy are allowed (back-compat with a legacy bridge).
    """
    if agent_info is None:
        return True
    if agent_info.get("is_orchestrator"):
        return False
    agent_class = str(agent_info.get("agent_class") or "").lower()
    if agent_class and agent_class != "agent":
        return False
    substrate = str(agent_info.get("identity_substrate") or "").lower()
    return substrate != "none"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the conversation platform: one entity per bridge agent (US0025)."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    client: BridgeClient = data["client"]
    coordinator = data.get("coordinator")
    agents_by_id: dict[str, dict[str, Any]] = {}
    if coordinator is not None and coordinator.data:
        agents_by_id = {a["id"]: a for a in coordinator.data["agents"]}

    for agent_id, agent_name, subentry_id, prompt in _agents_from_entry(config_entry):
        if not _is_voice_capable(agents_by_id.get(agent_id)):
            _LOGGER.debug(
                "Skipping %s as a voice entity (not a full agent identity)",
                agent_id,
            )
            continue
        entity = AgentBridgeConversationEntity(
            config_entry,
            client,
            agent_id=agent_id,
            agent_name=agent_name,
            subentry_id=subentry_id,
            prompt=prompt,
        )
        if subentry_id is not None:
            async_add_entities([entity], config_subentry_id=subentry_id)
        else:
            async_add_entities([entity])
        _LOGGER.debug("Added conversation entity for agent %s", agent_id)


class AgentBridgeConversationEntity(ConversationEntity):
    """A Home Assistant ``ConversationEntity`` backed by one bridge agent."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        client: BridgeClient,
        *,
        agent_id: str,
        agent_name: str,
        subentry_id: str | None = None,
        prompt: str = DEFAULT_PROMPT,
    ) -> None:
        """Initialise the entity for a single bridge agent."""
        self.entry = entry
        self.client = client
        self._agent_id = agent_id
        self._prompt = prompt
        self._attr_name = agent_name
        unique_suffix = subentry_id or agent_id
        self._attr_unique_id = f"{entry.entry_id}_{unique_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=agent_name,
            manufacturer="Agent Bridge",
            model=agent_id,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def supported_languages(self) -> list[str] | str:
        """Return supported languages (delegate to the AI model)."""
        return MATCH_ALL

    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: ChatLog,
    ) -> conversation.ConversationResult:
        """Handle one conversation turn via ``ChatLog`` (US0026).

        Forwards the utterance + a grounding hint as free text to this entity's
        bridge agent and returns the reply. Actuation is the agent's own job
        (US0027); no HA tool loop runs here.
        """
        options = self.entry.options

        # Ensure the user's turn is in the log. The base async_process path adds it
        # via async_get_chat_log; this guard keeps direct invocation (tests) correct.
        if not chat_log.content or chat_log.content[-1].role != "user":
            chat_log.async_add_user_content(UserContent(user_input.text))

        is_voice = user_input.device_id is not None
        # Typed field reads (US0029/AC2) -- no getattr reflection; satellite_id and
        # extra_system_prompt are first-class on ConversationInput in modern HA.
        satellite_id = user_input.satellite_id
        area_name = _resolve_area_name(self.hass, satellite_id or user_input.device_id)

        # Entity grounding hint (names/areas/aliases) -- a hint, not state authority.
        exposed_ids = await async_get_exposed_entities(self.hass, self.entity_id)
        entity_context = build_entity_context(
            self.hass,
            exposed_ids,
            max_chars=options.get(CONF_CONTEXT_MAX_CHARS, DEFAULT_CONTEXT_MAX_CHARS),
            strategy=options.get(CONF_CONTEXT_STRATEGY, DEFAULT_CONTEXT_STRATEGY),
        )
        risky_domains = _risky_domains_present(exposed_ids)
        extra_prompt = user_input.extra_system_prompt
        caution = _safety_caution(risky_domains)
        if caution:
            extra_prompt = f"{extra_prompt}\n\n{caution}" if extra_prompt else caution
        system_prompt = _build_system_prompt(
            instructions=self._prompt,
            area_name=area_name,
            entity_context=entity_context,
            extra_system_prompt=extra_prompt,
        )

        # History is sourced from ChatLog (US0026/AC2), not SessionManager.
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            *_messages_from_chat_log(chat_log),
        ]

        metadata: dict[str, Any] | None = None
        if is_voice:
            metadata = {
                "source": "voice",
                "device_id": user_input.device_id,
                "area": area_name,
                "language": user_input.language,
            }
            if satellite_id:
                metadata["satellite_id"] = satellite_id

        if options.get(CONF_DEBUG_LOGGING, False):
            _LOGGER.info(
                "Conversation turn: agent=%s conversation=%s area=%s voice=%s",
                self._agent_id,
                chat_log.conversation_id,
                area_name,
                is_voice,
            )

        response: dict[str, Any] = {}
        try:
            response = await self.client.chat(
                messages,
                agent=self._agent_id,
                channel=chat_log.conversation_id,
                metadata=metadata,
            )
            text = extract_response_text(response) or ""
        except BridgeError as err:
            text = ERROR_MESSAGES.get(err.code, str(err))

        chat_log.async_add_assistant_content_without_tools(
            AssistantContent(agent_id=self.entity_id, content=text)
        )

        model = response.get("model", "") if isinstance(response, dict) else ""
        self.hass.bus.async_fire(
            EVENT_MESSAGE_RECEIVED,
            {
                "agent_id": self._agent_id,
                "model": model,
                "content_preview": text[:200],
            },
        )

        # US0027/AC3: actuation audit surface. The agent actuates HA itself via its
        # own /api/mcp mount and emits the authoritative per-actuation event from
        # there; this HA-side event is the documented hook point US0031 wires to the
        # bridge audit log, recording the reactive turn that could actuate.
        self.hass.bus.async_fire(
            EVENT_ACTUATION_AUDIT,
            {
                "agent_id": self._agent_id,
                "conversation_id": chat_log.conversation_id,
                "area": area_name,
                "is_voice": is_voice,
                "risky_domains_exposed": sorted(risky_domains),
                "reply_preview": text[:200],
            },
        )

        intent_response = intent.IntentResponse(language=user_input.language)
        intent_response.async_set_speech(text)

        return conversation.ConversationResult(
            response=intent_response,
            conversation_id=chat_log.conversation_id,
            continue_conversation=_detect_continuation(text),
        )
