"""Shared test fixtures for Agent Bridge HA."""

from __future__ import annotations

# Patch ConversationResult for HA versions that lack continue_conversation.
# ConversationResult is a dataclass with __slots__, so we replace it entirely.
import dataclasses as _dc
import inspect as _inspect
from homeassistant.components import conversation as _conv_mod
_CR = _conv_mod.ConversationResult
if "continue_conversation" not in _inspect.signature(_CR.__init__).parameters:
    @_dc.dataclass(slots=True)
    class _PatchedConversationResult:
        response: object
        conversation_id: str | None = None
        continue_conversation: bool = False
        def as_dict(self):
            return _dc.asdict(self)
    _conv_mod.ConversationResult = _PatchedConversationResult

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.agent_bridge.client import BridgeClient
from custom_components.agent_bridge.const import (
    CONF_BRIDGE_TOKEN,
    CONF_BRIDGE_URL,
    CONF_CONTEXT_MAX_CHARS,
    CONF_CONTEXT_STRATEGY,
    CONF_DEBUG_LOGGING,
    CONF_DEFAULT_AGENT,
    CONF_ENABLE_PER_AGENT,
    CONF_ENABLE_TOOL_CALLS,
    CONF_SSL_VERIFY,
    CONF_THINKING_TIMEOUT,
    CONF_VOICE_AGENT,
    DEFAULT_CONTEXT_MAX_CHARS,
    DEFAULT_CONTEXT_STRATEGY,
    DEFAULT_THINKING_TIMEOUT,
    DOMAIN,
)

MOCK_BRIDGE_URL = "http://10.0.0.206:18780"
MOCK_TOKEN = "test-bridge-token-123"


@pytest.fixture(autouse=True)
def _bypass_frame_usage_report():
    """No-op HA's advisory frame.report_usage during unit tests.

    HA 2026's ``DataUpdateCoordinator.__init__`` (and some bus paths) call
    ``frame.report_usage(...)`` for telemetry, which raises "Frame helper not set
    up" when a test passes a ``MagicMock`` hass instead of the full ``hass``
    fixture. The report is advisory (which integration is calling), not behaviour,
    so stubbing it keeps these fast unit tests valid on a current HA core
    (the version pin that EP0007/US0029 requires).
    """
    with patch("homeassistant.helpers.frame.report_usage"):
        yield


@pytest.fixture
def mock_config_entry_data() -> dict[str, Any]:
    """Return standard config entry data."""
    return {
        CONF_BRIDGE_URL: MOCK_BRIDGE_URL,
        CONF_BRIDGE_TOKEN: MOCK_TOKEN,
        CONF_DEFAULT_AGENT: "cora",
        CONF_VOICE_AGENT: "cora",
    }


@pytest.fixture
def mock_config_entry_options() -> dict[str, Any]:
    """Return standard config entry options."""
    return {
        CONF_CONTEXT_MAX_CHARS: DEFAULT_CONTEXT_MAX_CHARS,
        CONF_CONTEXT_STRATEGY: DEFAULT_CONTEXT_STRATEGY,
        CONF_ENABLE_PER_AGENT: False,
        CONF_ENABLE_TOOL_CALLS: True,
        CONF_THINKING_TIMEOUT: DEFAULT_THINKING_TIMEOUT,
        CONF_SSL_VERIFY: True,
        CONF_DEBUG_LOGGING: False,
    }


@pytest.fixture
def mock_config_entry(mock_config_entry_data, mock_config_entry_options):
    """Return a mock ConfigEntry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = mock_config_entry_data
    entry.options = mock_config_entry_options
    entry.title = "Agent Bridge"
    return entry


@pytest.fixture
def mock_session():
    """Return a mock aiohttp.ClientSession."""
    session = AsyncMock()
    return session


@pytest.fixture
def mock_client(mock_session):
    """Return a mock BridgeClient."""
    client = MagicMock(spec=BridgeClient)
    client.check_alive = AsyncMock(return_value=True)
    client.health = AsyncMock(return_value=HEALTH_SHALLOW_OK)
    client.discover = AsyncMock(return_value=DISCOVERY_THREE_AGENTS)
    client.chat = AsyncMock(return_value=CHAT_SUCCESS)
    client.invoke_tool = AsyncMock(return_value={"result": "ok"})
    return client


# --- Canned responses ---

HEALTH_SHALLOW_OK: dict[str, Any] = {
    "status": "ok",
    "version": "3.2.0",
    "uptime_seconds": 12345,
    "mode": "primary",
    "agents": {"total": 3, "healthy": 3},
}

HEALTH_SHALLOW_DEGRADED: dict[str, Any] = {
    "status": "degraded",
    "version": "3.2.0",
    "uptime_seconds": 5000,
    "mode": "primary",
    "agents": {"total": 3, "healthy": 1},
}

HEALTH_DEEP: dict[str, Any] = {
    "status": "ok",
    "version": "3.2.0",
    "uptime_seconds": 12345,
    "mode": "primary",
    "agents": {
        "cora": {"status": "healthy", "adapter": "http-openai", "latencyMs": 120},
        "claude": {"status": "healthy", "adapter": "cli", "latencyMs": 500},
        "prof": {"status": "unhealthy", "adapter": "http-openai", "error": "timeout"},
    },
}

DISCOVERY_THREE_AGENTS: list[dict[str, Any]] = [
    {
        "id": "cora",
        "name": "Cora",
        "description": "Primary AI assistant",
        "status": "healthy",
        "adapter": "http-openai",
        "capabilities": {"chat": True, "tools": ["web_search"], "streaming": True},
        "tags": ["primary"],
    },
    {
        "id": "claude",
        "name": "Claude",
        "description": "Code assistant",
        "status": "healthy",
        "adapter": "cli",
        "capabilities": {"chat": True, "tools": [], "streaming": False},
        "tags": ["code"],
    },
    {
        "id": "prof",
        "name": "Prof",
        "description": "Research agent",
        "status": "unhealthy",
        "adapter": "http-openai",
        "capabilities": {"chat": True, "tools": ["web_search"], "streaming": True},
        "tags": ["research"],
    },
]

DISCOVERY_EMPTY: list[dict[str, Any]] = []

CHAT_SUCCESS: dict[str, Any] = {
    "id": "chatcmpl-abc123",
    "object": "chat.completion",
    "created": 1712345678,
    "model": "kimi-k2.5:cloud",
    "agent": "cora",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "I've turned on the kitchen lights.",
            },
            "finish_reason": "stop",
        }
    ],
    "usage": {"input_tokens": 1200, "output_tokens": 45},
}

CHAT_WITH_TOOL_CALLS: dict[str, Any] = {
    "id": "chatcmpl-def456",
    "object": "chat.completion",
    "model": "kimi-k2.5:cloud",
    "agent": "cora",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_abc123",
                        "type": "function",
                        "function": {
                            "name": "execute_service",
                            "arguments": '{"domain": "light", "service": "turn_on", "entity_id": "light.kitchen"}',
                        },
                    }
                ],
            },
            "finish_reason": "tool_calls",
        }
    ],
}

CHAT_WITH_CONTENT_AND_TOOLS: dict[str, Any] = {
    "id": "chatcmpl-ghi789",
    "object": "chat.completion",
    "model": "kimi-k2.5:cloud",
    "agent": "cora",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Sure, I'll turn on the lights.",
                "tool_calls": [
                    {
                        "id": "call_xyz",
                        "type": "function",
                        "function": {
                            "name": "execute_service",
                            "arguments": '{"domain": "light", "service": "turn_on", "entity_id": "light.kitchen"}',
                        },
                    }
                ],
            },
            "finish_reason": "tool_calls",
        }
    ],
}

CHAT_QUESTION_RESPONSE: dict[str, Any] = {
    "id": "chatcmpl-q1",
    "object": "chat.completion",
    "model": "kimi-k2.5:cloud",
    "agent": "cora",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Would you like me to turn on all the lights?",
            },
            "finish_reason": "stop",
        }
    ],
}

BRIDGE_ERROR_TIMEOUT: dict[str, Any] = {
    "error": {
        "code": "AGENT_TIMEOUT",
        "message": "Agent cora did not respond within 120s",
        "agent": "cora",
        "retryable": True,
    }
}
