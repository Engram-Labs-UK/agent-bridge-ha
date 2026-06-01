"""Constants for the Agent Bridge integration."""

from __future__ import annotations

DOMAIN = "agent_bridge"
PLATFORMS: list[str] = ["sensor", "binary_sensor", "event"]

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

# Defaults
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
MAX_TOOL_ITERATIONS = 10  # tool call loop cap (ADR-005)

# Event types (HA bus)
EVENT_MESSAGE_RECEIVED = f"{DOMAIN}_message_received"
EVENT_TOOL_INVOKED = f"{DOMAIN}_tool_invoked"
EVENT_AGENT_DISCOVERED = f"{DOMAIN}_agent_discovered"
EVENT_AGENT_REMOVED = f"{DOMAIN}_agent_removed"
EVENT_BRIDGE_UPGRADED = f"{DOMAIN}_bridge_upgraded"

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
