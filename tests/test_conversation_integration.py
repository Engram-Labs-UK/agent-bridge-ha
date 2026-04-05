"""Integration tests for conversation agent -- full process flow with mocked bridge."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

import pytest

from custom_components.agent_bridge.conversation import (
    AgentBridgeConversationAgent,
    PerAgentConversationAgent,
    async_setup_conversation_agent,
    async_setup_per_agent_conversations,
    async_unload_conversation_agent,
    async_remove_per_agent_conversation,
    _json_str,
    ERROR_MESSAGES,
)
from custom_components.agent_bridge.client import BridgeClient, BridgeError
from custom_components.agent_bridge.const import (
    CONF_CONTEXT_MAX_CHARS,
    CONF_CONTEXT_STRATEGY,
    CONF_DEBUG_LOGGING,
    CONF_DEFAULT_AGENT,
    CONF_ENABLE_TOOL_CALLS,
    CONF_VOICE_AGENT,
    DEFAULT_CONTEXT_MAX_CHARS,
    DEFAULT_CONTEXT_STRATEGY,
    DOMAIN,
)
from custom_components.agent_bridge import SessionManager

from .conftest import CHAT_SUCCESS, CHAT_WITH_TOOL_CALLS, CHAT_QUESTION_RESPONSE


def _make_conversation_input(
    text="Turn on the lights",
    device_id=None,
    language="en",
):
    """Create a mock ConversationInput."""
    inp = MagicMock(spec=[
        "text", "device_id", "language", "conversation_id",
    ])
    inp.text = text
    inp.device_id = device_id
    inp.language = language
    inp.conversation_id = None
    return inp


def _make_hass_with_bridge(
    chat_response=None,
    options=None,
    data=None,
):
    """Create a hass mock with bridge data pre-wired."""
    hass = MagicMock()
    hass.bus.async_fire = MagicMock()

    client = MagicMock(spec=BridgeClient)
    client.chat = AsyncMock(return_value=chat_response or CHAT_SUCCESS)

    sm = SessionManager.__new__(SessionManager)
    sm._sessions = {}
    sm._store = MagicMock()
    sm._store.async_save = AsyncMock()

    entry_data = data or {
        CONF_DEFAULT_AGENT: "cora",
        CONF_VOICE_AGENT: "cora",
    }
    entry_options = options or {
        CONF_CONTEXT_MAX_CHARS: DEFAULT_CONTEXT_MAX_CHARS,
        CONF_CONTEXT_STRATEGY: DEFAULT_CONTEXT_STRATEGY,
        CONF_ENABLE_TOOL_CALLS: True,
        CONF_DEBUG_LOGGING: False,
    }

    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = entry_data
    entry.options = entry_options

    hass.data = {
        DOMAIN: {
            "test_entry": {
                "client": client,
                "coordinator": MagicMock(),
                "session_manager": sm,
                "conversation_agent": None,
                "per_agent_entities": {},
            }
        }
    }

    return hass, entry, client, sm


class TestAgentBridgeConversationAgent:

    @pytest.mark.asyncio
    async def test_process_text_input(self):
        hass, entry, client, sm = _make_hass_with_bridge()

        with patch(
            "custom_components.agent_bridge.conversation.async_get_exposed_entities",
            new_callable=AsyncMock,
            return_value=["light.kitchen"],
        ), patch(
            "custom_components.agent_bridge.conversation.build_entity_context",
            return_value="Kitchen Light (light.kitchen): on",
        ):
            agent = AgentBridgeConversationAgent(hass, entry, client)
            user_input = _make_conversation_input(device_id=None)
            result = await agent.async_process(user_input)

        assert result.response.speech["plain"]["speech"] == "I've turned on the kitchen lights."
        assert result.conversation_id.startswith("agent-cora-")

    @pytest.mark.asyncio
    async def test_process_voice_input(self):
        hass, entry, client, sm = _make_hass_with_bridge()

        with patch(
            "custom_components.agent_bridge.conversation.async_get_exposed_entities",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "custom_components.agent_bridge.conversation.build_entity_context",
            return_value="",
        ), patch(
            "custom_components.agent_bridge.conversation._resolve_area_name",
            return_value="Kitchen",
        ):
            agent = AgentBridgeConversationAgent(hass, entry, client)
            user_input = _make_conversation_input(device_id="device_123")
            result = await agent.async_process(user_input)

        # Verify metadata was sent with voice request
        call_kwargs = client.chat.call_args
        metadata = call_kwargs.kwargs.get("metadata") or call_kwargs[1].get("metadata")
        assert metadata["source"] == "voice"
        assert metadata["device_id"] == "device_123"
        assert metadata["area"] == "Kitchen"

    @pytest.mark.asyncio
    async def test_process_with_tool_calls(self):
        # First call returns tool_calls, second call returns final response
        hass, entry, client, sm = _make_hass_with_bridge(
            chat_response=CHAT_WITH_TOOL_CALLS
        )
        # After tool execution, bridge returns final response
        client.chat = AsyncMock(
            side_effect=[CHAT_WITH_TOOL_CALLS, CHAT_SUCCESS]
        )

        with patch(
            "custom_components.agent_bridge.conversation.async_get_exposed_entities",
            new_callable=AsyncMock,
            return_value=["light.kitchen"],
        ), patch(
            "custom_components.agent_bridge.conversation.build_entity_context",
            return_value="",
        ), patch(
            "custom_components.agent_bridge.conversation.execute_tool_call",
            new_callable=AsyncMock,
            return_value={"success": True, "entity_id": "light.kitchen"},
        ):
            agent = AgentBridgeConversationAgent(hass, entry, client)
            user_input = _make_conversation_input()
            result = await agent.async_process(user_input)

        # Should have made 2 chat calls (tool_call + final)
        assert client.chat.call_count == 2
        assert "turned on" in result.response.speech["plain"]["speech"]

    @pytest.mark.asyncio
    async def test_tool_calls_disabled(self):
        hass, entry, client, sm = _make_hass_with_bridge(
            chat_response=CHAT_WITH_TOOL_CALLS,
            options={
                CONF_CONTEXT_MAX_CHARS: DEFAULT_CONTEXT_MAX_CHARS,
                CONF_CONTEXT_STRATEGY: DEFAULT_CONTEXT_STRATEGY,
                CONF_ENABLE_TOOL_CALLS: False,
                CONF_DEBUG_LOGGING: False,
            },
        )
        # When tools disabled, content is None in tool_calls response
        # The agent should extract None and return empty
        with patch(
            "custom_components.agent_bridge.conversation.async_get_exposed_entities",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "custom_components.agent_bridge.conversation.build_entity_context",
            return_value="",
        ):
            agent = AgentBridgeConversationAgent(hass, entry, client)
            user_input = _make_conversation_input()
            result = await agent.async_process(user_input)

        # Only 1 chat call (no tool loop)
        assert client.chat.call_count == 1

    @pytest.mark.asyncio
    async def test_bridge_error_returns_friendly_message(self):
        hass, entry, client, sm = _make_hass_with_bridge()
        client.chat = AsyncMock(
            side_effect=BridgeError("AGENT_TIMEOUT", "timed out")
        )

        with patch(
            "custom_components.agent_bridge.conversation.async_get_exposed_entities",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "custom_components.agent_bridge.conversation.build_entity_context",
            return_value="",
        ):
            agent = AgentBridgeConversationAgent(hass, entry, client)
            user_input = _make_conversation_input()
            result = await agent.async_process(user_input)

        speech = result.response.speech["plain"]["speech"]
        assert speech == ERROR_MESSAGES["AGENT_TIMEOUT"]

    @pytest.mark.asyncio
    async def test_continuation_detection(self):
        hass, entry, client, sm = _make_hass_with_bridge(
            chat_response=CHAT_QUESTION_RESPONSE
        )

        with patch(
            "custom_components.agent_bridge.conversation.async_get_exposed_entities",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "custom_components.agent_bridge.conversation.build_entity_context",
            return_value="",
        ):
            agent = AgentBridgeConversationAgent(hass, entry, client)
            user_input = _make_conversation_input()
            result = await agent.async_process(user_input)

        assert result.continue_conversation is True

    @pytest.mark.asyncio
    async def test_tool_loop_cap(self):
        """Agent that always returns tool_calls should be capped at 10 iterations."""
        hass, entry, client, sm = _make_hass_with_bridge()
        # Always return tool_calls
        client.chat = AsyncMock(return_value=CHAT_WITH_TOOL_CALLS)

        with patch(
            "custom_components.agent_bridge.conversation.async_get_exposed_entities",
            new_callable=AsyncMock,
            return_value=["light.kitchen"],
        ), patch(
            "custom_components.agent_bridge.conversation.build_entity_context",
            return_value="",
        ), patch(
            "custom_components.agent_bridge.conversation.execute_tool_call",
            new_callable=AsyncMock,
            return_value={"success": True, "entity_id": "light.kitchen"},
        ):
            agent = AgentBridgeConversationAgent(hass, entry, client)
            user_input = _make_conversation_input()
            result = await agent.async_process(user_input)

        assert client.chat.call_count == 10
        speech = result.response.speech["plain"]["speech"]
        assert speech == ERROR_MESSAGES["TOOL_LOOP"]

    @pytest.mark.asyncio
    async def test_debug_logging(self):
        hass, entry, client, sm = _make_hass_with_bridge(
            options={
                CONF_CONTEXT_MAX_CHARS: DEFAULT_CONTEXT_MAX_CHARS,
                CONF_CONTEXT_STRATEGY: DEFAULT_CONTEXT_STRATEGY,
                CONF_ENABLE_TOOL_CALLS: True,
                CONF_DEBUG_LOGGING: True,
            },
        )

        with patch(
            "custom_components.agent_bridge.conversation.async_get_exposed_entities",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "custom_components.agent_bridge.conversation.build_entity_context",
            return_value="",
        ), patch(
            "custom_components.agent_bridge.conversation._resolve_area_name",
            return_value="Kitchen",
        ), patch(
            "custom_components.agent_bridge.conversation._LOGGER"
        ) as mock_logger:
            agent = AgentBridgeConversationAgent(hass, entry, client)
            user_input = _make_conversation_input(device_id="dev_1")
            await agent.async_process(user_input)

        mock_logger.info.assert_called_once()
        args = mock_logger.info.call_args[0]
        assert "Voice routing" in args[0]

    @pytest.mark.asyncio
    async def test_fires_message_received_event(self):
        hass, entry, client, sm = _make_hass_with_bridge()

        with patch(
            "custom_components.agent_bridge.conversation.async_get_exposed_entities",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "custom_components.agent_bridge.conversation.build_entity_context",
            return_value="",
        ):
            agent = AgentBridgeConversationAgent(hass, entry, client)
            user_input = _make_conversation_input()
            await agent.async_process(user_input)

        hass.bus.async_fire.assert_called_once()
        event_name = hass.bus.async_fire.call_args[0][0]
        assert event_name == "agent_bridge_message_received"

    @pytest.mark.asyncio
    async def test_session_persistence(self):
        hass, entry, client, sm = _make_hass_with_bridge()

        with patch(
            "custom_components.agent_bridge.conversation.async_get_exposed_entities",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "custom_components.agent_bridge.conversation.build_entity_context",
            return_value="",
        ):
            agent = AgentBridgeConversationAgent(hass, entry, client)
            user_input = _make_conversation_input()
            result1 = await agent.async_process(user_input)
            result2 = await agent.async_process(user_input)

        # Same session ID for same agent
        assert result1.conversation_id == result2.conversation_id
        # Session was saved
        sm._store.async_save.assert_called()


class TestPerAgentConversationAgent:

    @pytest.mark.asyncio
    async def test_routes_to_fixed_agent(self):
        hass, entry, client, sm = _make_hass_with_bridge()

        with patch(
            "custom_components.agent_bridge.conversation.async_get_exposed_entities",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "custom_components.agent_bridge.conversation.build_entity_context",
            return_value="",
        ):
            agent = PerAgentConversationAgent(
                hass, entry, client, "claude", "Claude"
            )
            user_input = _make_conversation_input()
            result = await agent.async_process(user_input)

        # Should route to "claude" not "cora"
        call_kwargs = client.chat.call_args
        agent_arg = call_kwargs.kwargs.get("agent") or call_kwargs[1].get("agent")
        assert agent_arg == "claude"

    @pytest.mark.asyncio
    async def test_per_agent_session(self):
        hass, entry, client, sm = _make_hass_with_bridge()

        with patch(
            "custom_components.agent_bridge.conversation.async_get_exposed_entities",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "custom_components.agent_bridge.conversation.build_entity_context",
            return_value="",
        ):
            agent = PerAgentConversationAgent(
                hass, entry, client, "claude", "Claude"
            )
            user_input = _make_conversation_input()
            result = await agent.async_process(user_input)

        assert result.conversation_id.startswith("agent-claude-")


class TestSetupAndTeardown:

    @pytest.mark.asyncio
    async def test_setup_conversation_agent(self):
        hass = MagicMock()
        entry = MagicMock()
        entry.entry_id = "test_entry"
        client = MagicMock()

        hass.data = {
            DOMAIN: {
                "test_entry": {
                    "client": client,
                    "coordinator": MagicMock(),
                    "session_manager": MagicMock(),
                }
            }
        }

        with patch(
            "custom_components.agent_bridge.conversation.conversation.async_set_agent"
        ) as mock_set:
            await async_setup_conversation_agent(hass, entry)
        mock_set.assert_called_once()
        assert "conversation_agent" in hass.data[DOMAIN]["test_entry"]

    @pytest.mark.asyncio
    async def test_setup_per_agent_conversations(self):
        hass = MagicMock()
        entry = MagicMock()
        entry.entry_id = "test_entry"
        client = MagicMock()

        hass.data = {
            DOMAIN: {
                "test_entry": {
                    "client": client,
                    "per_agent_entities": {},
                }
            }
        }

        agents = [
            {"id": "cora", "name": "Cora", "capabilities": {"chat": True}},
            {"id": "knox", "name": "Knox", "capabilities": {"chat": False}},
        ]

        with patch(
            "custom_components.agent_bridge.conversation.conversation.async_set_agent"
        ):
            await async_setup_per_agent_conversations(hass, entry, agents)

        per_agent = hass.data[DOMAIN]["test_entry"]["per_agent_entities"]
        assert "cora" in per_agent
        assert "knox" not in per_agent  # chat: false

    @pytest.mark.asyncio
    async def test_remove_per_agent_conversation(self):
        hass = MagicMock()
        entry = MagicMock()
        entry.entry_id = "test_entry"

        hass.data = {
            DOMAIN: {
                "test_entry": {
                    "per_agent_entities": {"cora": MagicMock()},
                }
            }
        }

        with patch(
            "custom_components.agent_bridge.conversation.conversation.async_unset_agent"
        ):
            await async_remove_per_agent_conversation(hass, entry, "cora")

        assert "cora" not in hass.data[DOMAIN]["test_entry"]["per_agent_entities"]

    @pytest.mark.asyncio
    async def test_unload_conversation_agent(self):
        hass = MagicMock()
        entry = MagicMock()
        entry.entry_id = "test_entry"

        hass.data = {
            DOMAIN: {
                "test_entry": {
                    "per_agent_entities": {"cora": MagicMock(), "claude": MagicMock()},
                }
            }
        }

        with patch(
            "custom_components.agent_bridge.conversation.conversation.async_unset_agent"
        ) as mock_unset:
            await async_unload_conversation_agent(hass, entry)

        # Called for 2 per-agent + 1 primary
        assert mock_unset.call_count == 3


class TestJsonStr:

    def test_dict(self):
        result = _json_str({"a": 1})
        assert '"a"' in result

    def test_with_non_serializable(self):
        from datetime import datetime
        result = _json_str({"dt": datetime(2026, 1, 1)})
        assert "2026" in result
