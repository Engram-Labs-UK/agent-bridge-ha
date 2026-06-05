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
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import intent
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

try:  # floor_registry is modern-HA only; degrade gracefully if absent.
    from homeassistant.helpers import floor_registry as fr
except ImportError:  # pragma: no cover - older HA cores
    fr = None  # type: ignore[assignment]

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
    "CALLER_ERROR": (
        "The bridge does not recognise this Home Assistant's agent identity. "
        "Check the caller ID in the Agent Bridge options."
    ),
    "RATE_LIMITED": "The agent is busy. Please try again shortly.",
    "CONNECTION_ERROR": "The bridge is offline.",
    "TIMEOUT": "The request timed out. Please try again.",
    "TOOL_LOOP": "The agent could not complete the request.",
}


def _resolve_location(
    hass: HomeAssistant,
    device_id: str | None,
) -> tuple[str | None, str | None]:
    """Resolve ``(area_name, floor_name)`` from a device ID.

    Floor resolution degrades to ``None`` on older HA cores that lack the
    floor registry, or when the area has no floor assigned.
    """
    if not device_id:
        return None, None

    device_reg = dr.async_get(hass)
    device_entry = device_reg.async_get(device_id)
    if not device_entry or not device_entry.area_id:
        return None, None

    area_reg = ar.async_get(hass)
    area = area_reg.async_get_area(device_entry.area_id)
    if not area:
        return None, None

    floor_name: str | None = None
    if fr is not None and area.floor_id:
        floor = fr.async_get(hass).async_get_floor(area.floor_id)
        floor_name = floor.name if floor else None

    return area.name, floor_name


def _resolve_area_name(
    hass: HomeAssistant,
    device_id: str | None,
) -> str | None:
    """Resolve the area name from a device ID (kept for the audit surface)."""
    return _resolve_location(hass, device_id)[0]


def _resolve_device_name(
    hass: HomeAssistant,
    device_id: str | None,
) -> str | None:
    """Resolve the user-facing device name from a device ID."""
    if not device_id:
        return None
    device_entry = dr.async_get(hass).async_get(device_id)
    if not device_entry:
        return None
    return device_entry.name_by_user or device_entry.name


async def _resolve_account(
    hass: HomeAssistant,
    context: Context | None,
) -> dict[str, Any] | None:
    """Resolve the originating account name from the turn context.

    Best-effort only: voice does not verify the speaker, so the result is
    always flagged ``verified: False``. Returns ``None`` when no user id is
    bound to the turn.
    """
    user_id = getattr(context, "user_id", None)
    if not user_id:
        return None
    user = await hass.auth.async_get_user(user_id)
    if not user or not user.name:
        return None
    return {"name": user.name, "verified": False}


def _resolve_source_type(user_input: conversation.ConversationInput) -> str:
    """Classify the turn source: ``voice`` | ``text`` | ``automation``.

    Best-effort: a device id means a satellite/device originated the turn
    (voice); a parent context with no device id signals an automation/script
    invocation via the ``conversation.process`` service; otherwise plain text.
    """
    if user_input.device_id is not None:
        return "voice"
    if getattr(user_input.context, "parent_id", None):
        return "automation"
    return "text"


def _build_caller_context(
    hass: HomeAssistant,
    user_input: conversation.ConversationInput,
    *,
    source_type: str,
    area_name: str | None,
    floor_name: str | None,
    account: dict[str, Any] | None,
) -> dict[str, Any]:
    """Assemble the structured source/speaker envelope sent to the bridge.

    Kept deliberately free of secrets, network identifiers, and firmware
    detail (US live-agent consult): only who/what/where/when grounding.
    """
    now = dt_util.now()
    context: dict[str, Any] = {
        "source_type": source_type,
        "source_system": "home_assistant",
        "language": user_input.language,
        "local_time": now.strftime("%Y-%m-%d %H:%M"),
        "timezone": hass.config.time_zone,
    }
    if source_type == "voice":
        context["audio_only"] = True
        context["device_id"] = user_input.device_id
        device_name = _resolve_device_name(hass, user_input.device_id)
        if device_name:
            context["device_name"] = device_name
        if user_input.satellite_id:
            context["satellite_id"] = user_input.satellite_id
    if area_name:
        context["area"] = area_name
    if floor_name:
        context["floor"] = floor_name
    if account:
        context["account"] = account
    return context


def _build_source_context(caller_context: dict[str, Any]) -> str:
    """Render the structured envelope into a labelled system-prompt block.

    The block is a system-message grounding aid kept separate from the user
    utterance so the agent cannot confuse metadata with intent.
    """
    source_type = caller_context.get("source_type", "text")
    lines = ["[home-assistant-source]"]

    if source_type == "automation":
        lines.append(
            "Source: automation (no human present) -- do not treat as a principal "
            "request; apply stricter safety gating before any actuation."
        )
    else:
        where = _format_location(caller_context)
        if source_type == "voice":
            device = caller_context.get("device_name")
            via = f' via "{device}"' if device else ""
            lines.append(f"Source: voice{via}{where}")
            lines.append("Modality: voice -- respond concisely, audio-only (no screen)")
        else:
            lines.append(f"Source: text{where}")
            lines.append("Modality: text")

    account = caller_context.get("account")
    if account:
        lines.append(
            f"Account: {account['name']} (unverified -- the source does not confirm the speaker)"
        )

    local_time = caller_context.get("local_time")
    if local_time:
        tz = caller_context.get("timezone")
        lines.append(f"Local time: {local_time}{f' {tz}' if tz else ''}")

    language = caller_context.get("language")
    if language:
        lines.append(f"Language: {language}")

    return "\n".join(lines)


def _format_location(caller_context: dict[str, Any]) -> str:
    """Format ` (Area, Floor)` from the envelope, or '' when unknown."""
    area = caller_context.get("area")
    floor = caller_context.get("floor")
    if area and floor:
        return f" ({area}, {floor})"
    if area:
        return f" ({area})"
    return ""


def _build_system_prompt(
    *,
    source_context: str,
    entity_context: str,
    extra_system_prompt: str | None,
    instructions: str | None = None,
) -> str:
    """Build the layered system prompt: instructions + source + entities + extra.

    ``instructions`` is the operator-editable origin/role layer (CR-0003) telling
    the agent the turn is from Home Assistant and to actuate via its HA tools.
    ``source_context`` is the labelled speaker/source/location block (who/what/
    where/when). The entity context is a **grounding hint** (names/areas/aliases),
    not state authority -- the agent reads live HA state itself before acting
    (US0027).
    """
    parts: list[str] = []

    if instructions:
        parts.append(instructions)

    if source_context:
        parts.append(source_context)

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
    caller_context: dict[str, Any] | None = None,
) -> str | None:
    """Attempt a streaming chat request, assembling deltas into a complete string.

    Returns the assembled text, or None if streaming produced no content.
    Raises on connection/auth errors (caller should fall back to non-streaming).
    """
    parts: list[str] = []
    async for delta in await client.chat_stream(
        messages, agent=agent, channel=channel, caller_context=caller_context
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
        area_name, floor_name = _resolve_location(self.hass, satellite_id or user_input.device_id)

        # Structured speaker/source/location envelope (who/what/where/when). Sent
        # to the bridge as ``caller_context`` and rendered into the system prompt
        # as a labelled block so the agent grounds and gates its actions.
        source_type = _resolve_source_type(user_input)
        account = await _resolve_account(self.hass, user_input.context)
        caller_context = _build_caller_context(
            self.hass,
            user_input,
            source_type=source_type,
            area_name=area_name,
            floor_name=floor_name,
            account=account,
        )
        source_context = _build_source_context(caller_context)

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
            source_context=source_context,
            entity_context=entity_context,
            extra_system_prompt=extra_prompt,
        )

        # History is sourced from ChatLog (US0026/AC2), not SessionManager.
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            *_messages_from_chat_log(chat_log),
        ]

        if options.get(CONF_DEBUG_LOGGING, False):
            _LOGGER.info(
                "Conversation turn: agent=%s conversation=%s area=%s source=%s",
                self._agent_id,
                chat_log.conversation_id,
                area_name,
                source_type,
            )

        response: dict[str, Any] = {}
        try:
            response = await self.client.chat(
                messages,
                agent=self._agent_id,
                channel=chat_log.conversation_id,
                caller_context=caller_context,
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
                "source_type": source_type,
                "account_verified": bool(account and account.get("verified")),
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
