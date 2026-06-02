"""Tests for agent-selection filtering, crew picker, and editable instructions (CR-0003)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.agent_bridge.config_flow import ConversationSubentryFlowHandler
from custom_components.agent_bridge.const import (
    CONF_AGENT_ID,
    CONF_PROMPT,
    DEFAULT_PROMPT,
)
from custom_components.agent_bridge.helpers import agent_crew, is_selectable_agent

CORA = {"id": "cora", "name": "Cora", "agentClass": "agent", "identitySubstrate": "persona", "crew": "home"}
DBEE = {"id": "dbee", "name": "DBee", "agentClass": "agent", "identitySubstrate": "engram", "crew": "home"}
EVE = {"id": "eve", "name": "Eve", "agentClass": "agent", "identitySubstrate": "persona", "crew": "ops"}
MODEL = {"id": "openrouter-openai-gpt-4o", "name": "gpt-4o", "agentClass": "agent", "identitySubstrate": "none"}
CHATBOT = {"id": "faq", "name": "FAQ", "agentClass": "chatbot", "identitySubstrate": "persona"}
WORKER = {"id": "indexer", "name": "Indexer", "agentClass": "workerbot", "identitySubstrate": "persona"}
ORCH = {"id": "router", "name": "Router", "agentClass": "agent", "identitySubstrate": "persona", "isOrchestrator": True}
LEGACY = {"id": "old", "name": "Old"}  # no taxonomy


class TestIsSelectableAgent:
    def test_real_agents_selectable(self):
        assert is_selectable_agent(CORA)
        assert is_selectable_agent(DBEE)

    def test_bare_model_excluded(self):
        assert not is_selectable_agent(MODEL)

    def test_chatbot_and_workerbot_excluded(self):
        assert not is_selectable_agent(CHATBOT)
        assert not is_selectable_agent(WORKER)

    def test_orchestrator_excluded(self):
        assert not is_selectable_agent(ORCH)

    def test_legacy_allowed(self):
        assert is_selectable_agent(LEGACY)

    def test_agent_crew(self):
        assert agent_crew(CORA) == "home"
        assert agent_crew(MODEL) is None


def _handler(hass, agents):
    h = ConversationSubentryFlowHandler()
    h.hass = hass
    h._get_entry = MagicMock(return_value=MagicMock())
    return h


class TestSubentryFlow:
    @pytest.mark.asyncio
    async def test_crew_step_lists_crews(self, hass):
        h = _handler(hass, None)
        with patch(
            "custom_components.agent_bridge.config_flow._discover_agents",
            AsyncMock(return_value=[CORA, DBEE, EVE, MODEL, CHATBOT]),
        ):
            result = await h.async_step_user()
        assert result["type"] == "form"
        assert result["step_id"] == "user"
        # crew dropdown built from selectable agents only (home, ops), plus All crews
        schema_keys = result["data_schema"].schema
        crew_field = next(iter(schema_keys.values()))
        assert set(crew_field.container) == {"__all__", "home", "ops"}

    @pytest.mark.asyncio
    async def test_agent_step_filtered_by_crew_and_selectable(self, hass):
        h = _handler(hass, None)
        with patch(
            "custom_components.agent_bridge.config_flow._discover_agents",
            AsyncMock(return_value=[CORA, DBEE, EVE, MODEL, CHATBOT, WORKER]),
        ):
            await h.async_step_user()  # loads agents
            h._crew = "home"
            result = await h.async_step_agent()
        assert result["type"] == "form"
        assert result["step_id"] == "agent"
        agent_field = next(iter(result["data_schema"].schema.values()))
        # Only home-crew real agents; no models/chatbots/workerbots/ops
        assert set(agent_field.container) == {"cora", "dbee"}

    @pytest.mark.asyncio
    async def test_agent_step_creates_entry_with_default_prompt(self, hass):
        h = _handler(hass, None)
        h.async_create_entry = MagicMock(return_value={"type": "create_entry"})
        with patch(
            "custom_components.agent_bridge.config_flow._discover_agents",
            AsyncMock(return_value=[CORA, DBEE]),
        ):
            await h.async_step_user()
            await h.async_step_agent({CONF_AGENT_ID: "cora", CONF_PROMPT: DEFAULT_PROMPT})

        kwargs = h.async_create_entry.call_args.kwargs
        assert kwargs["title"] == "Cora"
        assert kwargs["data"][CONF_AGENT_ID] == "cora"
        assert kwargs["data"][CONF_PROMPT] == DEFAULT_PROMPT
        assert kwargs["data"]["crew"] == "home"

    @pytest.mark.asyncio
    async def test_reconfigure_updates_prompt(self, hass):
        h = _handler(hass, None)
        subentry = MagicMock()
        subentry.data = {CONF_AGENT_ID: "cora", CONF_PROMPT: DEFAULT_PROMPT, "crew": "home"}
        h._get_reconfigure_subentry = MagicMock(return_value=subentry)
        h.async_update_and_abort = MagicMock(return_value={"type": "abort"})

        await h.async_step_reconfigure({CONF_PROMPT: "Custom instructions."})

        data = h.async_update_and_abort.call_args.kwargs["data"]
        assert data[CONF_PROMPT] == "Custom instructions."
        assert data[CONF_AGENT_ID] == "cora"  # preserved


class TestPromptFolded:
    @pytest.mark.asyncio
    async def test_entity_folds_custom_prompt_into_system_message(self, hass):
        from homeassistant.components.conversation import ChatLog
        from homeassistant.core import Context
        from homeassistant.components import conversation as conv

        from custom_components.agent_bridge.conversation import (
            AgentBridgeConversationEntity,
        )
        from .conftest import CHAT_SUCCESS

        client = MagicMock()
        client.chat = AsyncMock(return_value=CHAT_SUCCESS)
        entry = MagicMock()
        entry.entry_id = "e1"
        entry.options = {}
        entry.data = {}
        entity = AgentBridgeConversationEntity(
            entry, client, agent_id="cora", agent_name="Cora",
            prompt="You are Cora at home.",
        )
        entity.hass = hass
        entity.entity_id = "conversation.cora"
        chat_log = ChatLog(hass, "c1")

        ui = conv.ConversationInput(
            text="hi", context=Context(), conversation_id="c1",
            device_id=None, satellite_id=None, language="en", agent_id="conversation.cora",
        )
        with patch(
            "custom_components.agent_bridge.conversation.async_get_exposed_entities",
            AsyncMock(return_value=[]),
        ), patch(
            "custom_components.agent_bridge.conversation.build_entity_context",
            return_value="",
        ):
            await entity._async_handle_message(ui, chat_log)

        system_msg = client.chat.call_args.args[0][0]["content"]
        assert "You are Cora at home." in system_msg
