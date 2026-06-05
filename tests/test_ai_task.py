"""Tests for the AI Task platform (US0039). CI-gated (needs HA ai_task component)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.agent_bridge.ai_task import (
    AgentBridgeAITaskEntity,
    _strip_code_fence,
)


class TestStripCodeFence:
    def test_plain_json(self):
        assert _strip_code_fence('{"a": 1}') == '{"a": 1}'

    def test_json_fence(self):
        assert _strip_code_fence('```json\n{"a": 1}\n```') == '{"a": 1}'

    def test_bare_fence(self):
        assert _strip_code_fence('```\n{"b": 2}\n```') == '{"b": 2}'

    def test_whitespace(self):
        assert _strip_code_fence('  {"c": 3}  ') == '{"c": 3}'


def _entity(client):
    entry = MagicMock()
    entry.entry_id = "entry_1"
    return AgentBridgeAITaskEntity(entry, client, agent_id="cora", agent_name="Cora")


def _chat_log(user_text="Summarise the day"):
    log = MagicMock()
    log.conversation_id = "conv-1"
    content = MagicMock()
    content.role = "user"
    content.content = user_text
    log.content = [content]
    return log


class TestGenerateData:
    @pytest.mark.asyncio
    async def test_free_text_when_no_structure(self):
        client = MagicMock()
        client.chat = AsyncMock(
            return_value={"choices": [{"message": {"content": "A calm day."}}]}
        )
        entity = _entity(client)
        task = MagicMock(structure=None)

        result = await entity._async_generate_data(task, _chat_log())
        assert result.data == "A calm day."

    @pytest.mark.asyncio
    async def test_structured_json_parsed(self):
        client = MagicMock()
        client.chat = AsyncMock(
            return_value={"choices": [{"message": {"content": '```json\n{"count": 3}\n```'}}]}
        )
        entity = _entity(client)
        task = MagicMock(structure={"count": int})

        result = await entity._async_generate_data(task, _chat_log())
        assert result.data == {"count": 3}

    @pytest.mark.asyncio
    async def test_invalid_json_raises(self):
        from homeassistant.exceptions import HomeAssistantError

        client = MagicMock()
        client.chat = AsyncMock(return_value={"choices": [{"message": {"content": "not json"}}]})
        entity = _entity(client)
        task = MagicMock(structure={"count": int})

        with pytest.raises(HomeAssistantError):
            await entity._async_generate_data(task, _chat_log())

    @pytest.mark.asyncio
    async def test_bridge_error_raises(self):
        from homeassistant.exceptions import HomeAssistantError

        from custom_components.agent_bridge.client import BridgeError

        client = MagicMock()
        client.chat = AsyncMock(side_effect=BridgeError("TIMEOUT", "x"))
        entity = _entity(client)
        task = MagicMock(structure=None)

        with pytest.raises(HomeAssistantError):
            await entity._async_generate_data(task, _chat_log())
