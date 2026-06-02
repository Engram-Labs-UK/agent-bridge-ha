"""Constants for the Agent Bridge integration."""

from __future__ import annotations

DOMAIN = "agent_bridge"
PLATFORMS: list[str] = ["conversation", "sensor", "binary_sensor", "event"]

# Config subentry type: one conversation entity per bridge agent (US0025).
SUBENTRY_TYPE_CONVERSATION = "conversation"
CONF_AGENT_ID = "agent_id"
CONF_CREW = "crew"  # crew the agent belongs to (CR-0003 crew-scoped picker)
CONF_PROMPT = "prompt"  # editable per-agent instructions folded into the system prompt

# Default instructions folded into the system prompt so the agent knows the turn
# originates from Home Assistant and should actuate via its HA tools (CR-0003).
# Operator-editable per agent in the subentry config.
DEFAULT_PROMPT = (
    "This request comes from Home Assistant Assist. You are the user's home "
    "agent: read and actuate Home Assistant devices via your Home Assistant "
    "tools, confirm safety-relevant actions (locks, alarms, heating, external "
    "doors) before acting, and read the device's live state back to verify the "
    "result. Keep replies concise and suitable for voice."
)

# Config entry keys
CONF_BRIDGE_URL = "bridge_url"
CONF_BRIDGE_TOKEN = "bridge_token"
CONF_DEFAULT_AGENT = "default_agent"
CONF_VOICE_AGENT = "voice_agent"
CONF_CONTEXT_MAX_CHARS = "context_max_chars"
CONF_CONTEXT_STRATEGY = "context_strategy"
CONF_ENABLE_PER_AGENT = "enable_per_agent_entities"
CONF_ENABLE_TOOL_CALLS = "enable_tool_calls"
CONF_THINKING_TIMEOUT = "thinking_timeout"
CONF_SSL_VERIFY = "ssl_verify"
CONF_DEBUG_LOGGING = "debug_logging"
CONF_CALLER_ID = "caller_id"  # x-bridge-mcp-caller identity (US0028/G9)

# Defaults
DEFAULT_CALLER_ID = "homeassistant"
DEFAULT_BRIDGE_URL = "http://localhost:18780"
DEFAULT_CONTEXT_MAX_CHARS = 13000
DEFAULT_CONTEXT_STRATEGY = "truncate"
DEFAULT_THINKING_TIMEOUT = 120
DEFAULT_POLL_INTERVAL = 30  # seconds
DEFAULT_DISCOVERY_INTERVAL = 300  # seconds
DEFAULT_TOOL_TIMEOUT = 10  # seconds per service call
DEFAULT_STREAMING_TIMEOUT = 300  # seconds
MAX_ENTITIES = 250
MAX_TEXT_DEPTH = 8  # recursive response text extraction depth

# Drift baselines (US0029). The integration is built+tested against these; the
# agent-context drift check raises an HA repair issue when the live bridge moves
# past the baseline, and CI pins the HA core.
TESTED_BRIDGE_VERSION = "4.36.0"
TESTED_HA_VERSION = "2026.2.3"

# v4.36 capability-envelope classes that may become HA voice entities (US0028/AC3).
# Orchestrators / workerbots are excluded -- they are not conversational front-ends.
VOICE_CAPABLE_ENVELOPES = frozenset({"chatbot", "agent", "assistant"})
MAX_TOOL_ITERATIONS = 10  # tool call loop cap (ADR-005)

# Event types (HA bus)
EVENT_MESSAGE_RECEIVED = f"{DOMAIN}_message_received"
EVENT_TOOL_INVOKED = f"{DOMAIN}_tool_invoked"
EVENT_AGENT_DISCOVERED = f"{DOMAIN}_agent_discovered"
EVENT_AGENT_REMOVED = f"{DOMAIN}_agent_removed"
EVENT_BRIDGE_UPGRADED = f"{DOMAIN}_bridge_upgraded"

# Actuation audit surface (US0027/AC3). The agent actuates HA itself via its own
# /api/mcp mount; this HA-side event is the documented hook point that US0031 wires
# to the bridge audit log (one audit surface, Rule 3). Fired once per reactive turn.
EVENT_ACTUATION_AUDIT = f"{DOMAIN}_actuation_audit"

# Safety-relevant domains the agent must confirm before actuating (US0027 deny/confirm
# list; from the US0021 live-fleet consult). The conversation entity folds a caution
# into the grounding prompt when any exposed entity is in one of these domains.
DENY_CONFIRM_DOMAINS = frozenset(
    {
        "lock",  # door/cabinet locks
        "alarm_control_panel",  # intruder alarms
        "climate",  # heating/cooling
        "water_heater",  # heating
        "cover",  # external doors / garage / gates
    }
)

# Bridge webhook event catalogue (v4.36 -- US0024/G10).
# bridge:upgraded is the drift signal the CR-0002 audit is about; it must be
# observed, not polled for.
BRIDGE_WEBHOOK_EVENTS = (
    "agent:registered",
    "agent:unregistered",
    "agent:updated",
    "agent:health-changed",
    "message:error",
    "bridge:upgraded",
)

# Response text extraction priority keys
TEXT_PRIORITY_KEYS = ("text", "content", "message", "output_text")

# Continuation detection defaults
DEFAULT_CONTINUATION_PHRASES = (
    "would you like",
    "shall i",
    "do you want",
    "should i",
    "which one",
    "what would you prefer",
)
DEFAULT_CONTINUATION_EXCLUSIONS = (
    "right?",
    "isn't it?",
    "okay?",
    "yeah?",
    "let me know if you need anything",
)
