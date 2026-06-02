"""Integration tests for the ConversationEntity -- _async_handle_message + ChatLog.

EP0007 R2 (US0025/US0026): the legacy AbstractConversationAgent + async_set_agent
path is retired in favour of one ConversationEntity per bridge agent (via config
subentries) using HA's ChatLog. These tests exercise the new entity against a real
``hass`` and a real ``ChatLog``, with the bridge client mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components import conversation
from homeassistant.components.conversation import (
    AssistantContent,
    ChatLog,
    UserContent,
)
from homeassistant.core import Context

from custom_components.agent_bridge.client import BridgeError
from custom_components.agent_bridge.conversation import (
    ERROR_MESSAGES,
    AgentBridgeConversationEntity,
    async_setup_entry,
)
from custom_components.agent_bridge.const import (
    CONF_AGENT_ID,
    CONF_DEFAULT_AGENT,
    DOMAIN,
    EVENT_MESSAGE_RECEIVED,
    SUBENTRY_TYPE_CONVERSATION,
)

from .conftest import CHAT_QUESTION_RESPONSE, CHAT_SUCCESS


def _conversation_input(
    text: str = "Turn on the lights",
    *,
    device_id: str | None = None,
    conversation_id: str | None = "conv-1",
    language: str = "en",
) -> conversation.ConversationInput:
    """Build a ConversationInput for tests."""
    return conversation.ConversationInput(
        text=text,
        context=Context(),
        conversation_id=conversation_id,
        device_id=device_id,
        satellite_id=None,
        language=language,
        agent_id="conversation.agent_bridge_cora",
    )


def _make_entity(client: MagicMock, hass) -> AgentBridgeConversationEntity:
    """Build a wired-up entity for a single agent."""
    entry = MagicMock()
    entry.entry_id = "entry_1"
    entry.options = {}
    entry.data = {CONF_DEFAULT_AGENT: "cora"}
    entity = AgentBridgeConversationEntity(
        entry, client, agent_id="cora", agent_name="Cora"
    )
    entity.hass = hass
    entity.entity_id = "conversation.agent_bridge_cora"
    return entity


def _patch_grounding():
    """Patch the grounding-hint helpers (no exposed entities needed in tests)."""
    return (
        patch(
            "custom_components.agent_bridge.conversation.async_get_exposed_entities",
            AsyncMock(return_value=[]),
        ),
        patch(
            "custom_components.agent_bridge.conversation.build_entity_context",
            return_value="",
        ),
    )


class TestPlatformSetup:
    """US0025: one ConversationEntity per agent via async_setup_entry."""

    @pytest.mark.asyncio
    async def test_fallback_single_default_agent(self, hass):
        client = MagicMock()
        entry = MagicMock()
        entry.entry_id = "entry_1"
        entry.data = {CONF_DEFAULT_AGENT: "cora"}
        entry.options = {}
        entry.subentries = {}
        hass.data.setdefault(DOMAIN, {})["entry_1"] = {"client": client}

        added: list = []
        await async_setup_entry(hass, entry, lambda ents, **kw: added.extend(ents))
        assert len(added) == 1
        assert isinstance(added[0], AgentBridgeConversationEntity)

    @pytest.mark.asyncio
    async def test_one_entity_per_subentry(self, hass):
        client = MagicMock()
        entry = MagicMock()
        entry.entry_id = "entry_1"
        entry.data = {}
        entry.options = {}

        def _sub(agent_id, title):
            s = MagicMock()
            s.subentry_type = SUBENTRY_TYPE_CONVERSATION
            s.data = {CONF_AGENT_ID: agent_id}
            s.title = title
            return s

        entry.subentries = {
            "s1": _sub("cora", "Cora"),
            "s2": _sub("eve", "Eve"),
            "s3": _sub("dbee", "DBee"),
        }
        hass.data.setdefault(DOMAIN, {})["entry_1"] = {"client": client}

        added: list = []
        await async_setup_entry(hass, entry, lambda ents, **kw: added.extend(ents))

        assert len(added) == 3
        assert {e._agent_id for e in added} == {"cora", "eve", "dbee"}


class TestHandleMessage:
    """US0026: _async_handle_message + ChatLog."""

    @pytest.mark.asyncio
    async def test_appends_user_and_assistant_content(self, hass):
        client = MagicMock()
        client.chat = AsyncMock(return_value=CHAT_SUCCESS)
        entity = _make_entity(client, hass)
        chat_log = ChatLog(hass, "conv-1")

        p1, p2 = _patch_grounding()
        with p1, p2:
            result = await entity._async_handle_message(
                _conversation_input(), chat_log
            )

        # AC1: user + assistant content appended to the ChatLog.
        roles = [c.role for c in chat_log.content]
        assert "user" in roles and "assistant" in roles
        assistant = next(c for c in chat_log.content if c.role == "assistant")
        assert assistant.content == "I've turned on the kitchen lights."
        assert isinstance(result, conversation.ConversationResult)
        assert result.response.speech["plain"]["speech"] == (
            "I've turned on the kitchen lights."
        )

    @pytest.mark.asyncio
    async def test_forwards_free_text_no_tools(self, hass):
        """Refined Option A: free-text forward, no tools[] in the outbound body."""
        client = MagicMock()
        client.chat = AsyncMock(return_value=CHAT_SUCCESS)
        entity = _make_entity(client, hass)
        chat_log = ChatLog(hass, "conv-1")

        p1, p2 = _patch_grounding()
        with p1, p2:
            await entity._async_handle_message(_conversation_input(), chat_log)

        kwargs = client.chat.call_args.kwargs
        messages = client.chat.call_args.args[0]
        assert kwargs["agent"] == "cora"
        assert "tools" not in kwargs
        assert messages[0]["role"] == "system"
        assert any(m["role"] == "user" and "lights" in m["content"] for m in messages)

    @pytest.mark.asyncio
    async def test_history_sourced_from_chat_log(self, hass):
        """US0026/AC2: multi-turn history comes from ChatLog, not SessionManager."""
        client = MagicMock()
        client.chat = AsyncMock(return_value=CHAT_SUCCESS)
        entity = _make_entity(client, hass)

        chat_log = ChatLog(hass, "conv-1")
        chat_log.async_add_user_content(UserContent("what's the time?"))
        chat_log.async_add_assistant_content_without_tools(
            AssistantContent(agent_id="conversation.agent_bridge_cora", content="3pm")
        )

        p1, p2 = _patch_grounding()
        with p1, p2:
            await entity._async_handle_message(
                _conversation_input("and the date?"), chat_log
            )

        sent = client.chat.call_args.args[0]
        contents = [m["content"] for m in sent if m["role"] != "system"]
        assert "what's the time?" in contents
        assert "3pm" in contents
        assert "and the date?" in contents

    @pytest.mark.asyncio
    async def test_bridge_error_returns_friendly_message(self, hass):
        client = MagicMock()
        client.chat = AsyncMock(side_effect=BridgeError("AGENT_TIMEOUT", "timed out"))
        entity = _make_entity(client, hass)
        chat_log = ChatLog(hass, "conv-1")

        p1, p2 = _patch_grounding()
        with p1, p2:
            result = await entity._async_handle_message(
                _conversation_input(), chat_log
            )

        assert result.response.speech["plain"]["speech"] == (
            ERROR_MESSAGES["AGENT_TIMEOUT"]
        )

    @pytest.mark.asyncio
    async def test_continuation_detected(self, hass):
        client = MagicMock()
        client.chat = AsyncMock(return_value=CHAT_QUESTION_RESPONSE)
        entity = _make_entity(client, hass)
        chat_log = ChatLog(hass, "conv-1")

        p1, p2 = _patch_grounding()
        with p1, p2:
            result = await entity._async_handle_message(
                _conversation_input(), chat_log
            )

        assert result.continue_conversation is True

    @pytest.mark.asyncio
    async def test_fires_message_received_event(self, hass):
        client = MagicMock()
        client.chat = AsyncMock(return_value=CHAT_SUCCESS)
        entity = _make_entity(client, hass)
        chat_log = ChatLog(hass, "conv-1")

        events = []
        hass.bus.async_listen(EVENT_MESSAGE_RECEIVED, lambda e: events.append(e))

        p1, p2 = _patch_grounding()
        with p1, p2:
            await entity._async_handle_message(_conversation_input(), chat_log)
        await hass.async_block_till_done()

        assert len(events) == 1
        assert events[0].data["agent_id"] == "cora"

    @pytest.mark.asyncio
    async def test_voice_metadata_sent(self, hass):
        client = MagicMock()
        client.chat = AsyncMock(return_value=CHAT_SUCCESS)
        entity = _make_entity(client, hass)
        chat_log = ChatLog(hass, "conv-1")

        p1, p2 = _patch_grounding()
        with p1, p2:
            await entity._async_handle_message(
                _conversation_input(device_id="device-123"), chat_log
            )

        metadata = client.chat.call_args.kwargs["metadata"]
        assert metadata is not None
        assert metadata["source"] == "voice"
        assert metadata["device_id"] == "device-123"
