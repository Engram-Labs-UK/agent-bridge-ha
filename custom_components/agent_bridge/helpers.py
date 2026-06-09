"""Response text extraction and helper utilities."""

from __future__ import annotations

from typing import Any

from .const import (
    CONF_CALLER_ID,
    CONF_DEFAULT_AGENT,
    DEFAULT_CALLER_ID,
    MAX_TEXT_DEPTH,
    TEXT_PRIORITY_KEYS,
)


def resolve_caller_id(entry: Any) -> str:
    """Effective ``x-bridge-mcp-caller`` for a config entry (BG0004).

    Bridge v4.36 requires the caller to be a **registered agent id** so it can
    resolve the caller's crew for cross-agent dispatch; an unregistered literal like
    ``homeassistant`` is rejected with 403. Precedence:

    1. an explicit ``caller_id`` option (operator-set, e.g. a dedicated HA caller
       once the fleet provisions one -- US0031),
    2. the configured ``default_agent`` (always a registered agent, so chat works
       out of the box),
    3. ``DEFAULT_CALLER_ID`` as a last resort.
    """
    explicit = str(entry.options.get(CONF_CALLER_ID) or "").strip()
    if explicit:
        return explicit
    default_agent = str(entry.data.get(CONF_DEFAULT_AGENT) or "").strip()
    if default_agent:
        return default_agent
    return DEFAULT_CALLER_ID


def is_selectable_agent(raw: dict[str, Any]) -> bool:
    """Whether a discovered agent should appear in the voice-agent picker (CR-0003).

    Only full **agents** (an identity + tools + conversational) make sense as HA
    voice agents. Excludes, using the v4.36 taxonomy:
    - orchestrators (``isOrchestrator``),
    - chatbots (conversational but no tools -- can't actuate) and workerbots
      (tools but not conversational) -- i.e. any ``agentClass`` other than ``agent``,
    - bare model passthroughs (``identitySubstrate: 'none'`` -- e.g. ``openrouter-*``).

    Entries with no taxonomy at all (legacy/older bridge) are allowed, so the picker
    still works against a bridge that predates these fields.
    """
    if raw.get("isOrchestrator"):
        return False
    agent_class = str(raw.get("agentClass") or "").lower()
    if agent_class and agent_class != "agent":
        return False
    substrate = str(raw.get("identitySubstrate") or "").lower()
    return substrate != "none"


def agent_crew(raw: dict[str, Any]) -> str | None:
    """Return the crew an agent belongs to, or None (CR-0003).

    Per-agent crew membership is the agent's ``team``, exposed only under the
    ``/v1/discovery?include=crew`` projection as a nested ``crew: {team, ...}``
    block. Handles that shape, a nested ``id``, and a flat string defensively.
    """
    crew = raw.get("crew")
    if isinstance(crew, dict):
        team = crew.get("team") or crew.get("id")
        return str(team) if team else None
    if crew:
        return str(crew)
    team = raw.get("team")
    return str(team) if team else None


def agent_label(raw: dict[str, Any]) -> str:
    """Human label for an agent, shared by the pickers and the entities (BG0005).

    ``name (crew)`` when the crew is known (matching the options picker), else the
    bare name. Never the raw agent id -- the id is only a last-resort fallback when
    an agent has no name at all.
    """
    name = raw.get("name") or raw.get("id", "")
    crew = agent_crew(raw)
    return f"{name} ({crew})" if crew else name


def extract_response_text(data: Any, *, _depth: int = 0) -> str | None:
    """Extract text from a bridge response using priority key traversal.

    Handles varying response structures by checking priority keys at each level
    and recursing into nested dicts/lists up to MAX_TEXT_DEPTH levels.

    Fast path: OpenAI chat completion format (choices[0].message.content).
    """
    if data is None:
        return None

    if isinstance(data, str):
        return data

    if isinstance(data, (int, float, bool)):
        return str(data)

    if _depth >= MAX_TEXT_DEPTH:
        return None

    if isinstance(data, dict):
        # Fast path: OpenAI chat completion format
        if _depth == 0 and "choices" in data:
            choices = data["choices"]
            if isinstance(choices, list) and choices:
                message = choices[0].get("message", {})
                if isinstance(message, dict):
                    content = message.get("content")
                    if content is not None:
                        return str(content) if not isinstance(content, str) else content

        # Priority key check at this level
        for key in TEXT_PRIORITY_KEYS:
            if key in data:
                val = data[key]
                if isinstance(val, str):
                    return val
                if val is not None:
                    result = extract_response_text(val, _depth=_depth + 1)
                    if result is not None:
                        return result

        # Recurse into all dict values
        for val in data.values():
            if isinstance(val, (dict, list)):
                result = extract_response_text(val, _depth=_depth + 1)
                if result is not None:
                    return result

    if isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                result = extract_response_text(item, _depth=_depth + 1)
                if result is not None:
                    return result

    return None
