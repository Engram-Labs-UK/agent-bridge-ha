"""Tests for config flow and options flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.agent_bridge.config_flow import (
    AgentBridgeConfigFlow,
    AgentBridgeOptionsFlow,
    STEP_USER_SCHEMA,
)
from custom_components.agent_bridge.client import (
    BridgeAuthError,
    BridgeConnectionError,
)
from custom_components.agent_bridge.const import (
    CONF_BRIDGE_TOKEN,
    CONF_BRIDGE_URL,
    CONF_DEFAULT_AGENT,
    CONF_VOICE_AGENT,
    DEFAULT_BRIDGE_URL,
    DOMAIN,
)


class TestStepUserSchema:

    def test_default_url(self):
        schema_keys = {str(k): k for k in STEP_USER_SCHEMA.schema}
        url_key = schema_keys[CONF_BRIDGE_URL]
        assert url_key.default() == DEFAULT_BRIDGE_URL


class TestConfigFlow:

    @pytest.mark.asyncio
    async def test_step_user_shows_form(self):
        flow = AgentBridgeConfigFlow()
        flow.hass = MagicMock()
        result = await flow.async_step_user()
        assert result["type"] == "form"
        assert result["step_id"] == "user"

    @pytest.mark.asyncio
    async def test_step_user_connection_error(self):
        flow = AgentBridgeConfigFlow()
        flow.hass = MagicMock()

        with patch(
            "custom_components.agent_bridge.config_flow.async_get_clientsession"
        ), patch(
            "custom_components.agent_bridge.config_flow.BridgeClient"
        ) as MockClient:
            instance = MockClient.return_value
            instance.check_alive = AsyncMock(return_value=False)

            result = await flow.async_step_user(
                {CONF_BRIDGE_URL: "http://bad:18780", CONF_BRIDGE_TOKEN: "tok"}
            )
        assert result["errors"]["base"] == "cannot_connect"

    @pytest.mark.asyncio
    async def test_step_user_auth_error(self):
        flow = AgentBridgeConfigFlow()
        flow.hass = MagicMock()

        with patch(
            "custom_components.agent_bridge.config_flow.async_get_clientsession"
        ), patch(
            "custom_components.agent_bridge.config_flow.BridgeClient"
        ) as MockClient:
            instance = MockClient.return_value
            instance.check_alive = AsyncMock(return_value=True)
            instance.discover = AsyncMock(side_effect=BridgeAuthError())

            result = await flow.async_step_user(
                {CONF_BRIDGE_URL: "http://bridge:18780", CONF_BRIDGE_TOKEN: "bad"}
            )
        assert result["errors"]["base"] == "invalid_auth"

    @pytest.mark.asyncio
    async def test_step_user_no_agents(self):
        flow = AgentBridgeConfigFlow()
        flow.hass = MagicMock()

        with patch(
            "custom_components.agent_bridge.config_flow.async_get_clientsession"
        ), patch(
            "custom_components.agent_bridge.config_flow.BridgeClient"
        ) as MockClient:
            instance = MockClient.return_value
            instance.check_alive = AsyncMock(return_value=True)
            instance.discover = AsyncMock(return_value=[])

            result = await flow.async_step_user(
                {CONF_BRIDGE_URL: "http://bridge:18780", CONF_BRIDGE_TOKEN: "tok"}
            )
        assert result["errors"]["base"] == "no_agents"

    @pytest.mark.asyncio
    async def test_step_user_success_advances_to_agents(self):
        flow = AgentBridgeConfigFlow()
        flow.hass = MagicMock()

        agents = [
            {"id": "cora", "name": "Cora", "status": "healthy"},
            {"id": "claude", "name": "Claude", "status": "healthy"},
        ]

        with patch(
            "custom_components.agent_bridge.config_flow.async_get_clientsession"
        ), patch(
            "custom_components.agent_bridge.config_flow.BridgeClient"
        ) as MockClient:
            instance = MockClient.return_value
            instance.check_alive = AsyncMock(return_value=True)
            instance.discover = AsyncMock(return_value=agents)

            result = await flow.async_step_user(
                {CONF_BRIDGE_URL: "http://bridge:18780", CONF_BRIDGE_TOKEN: "tok"}
            )
        # Should advance to agents step
        assert result["type"] == "form"
        assert result["step_id"] == "agents"

    @pytest.mark.asyncio
    async def test_step_agents_creates_entry(self):
        flow = AgentBridgeConfigFlow()
        flow.hass = MagicMock()
        flow._bridge_url = "http://bridge:18780"
        flow._bridge_token = "tok"
        flow._agents = [{"id": "cora", "name": "Cora", "status": "healthy"}]

        # Mock unique ID methods
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()

        result = await flow.async_step_agents(
            {CONF_DEFAULT_AGENT: "cora", CONF_VOICE_AGENT: "cora"}
        )
        assert result["type"] == "create_entry"
        assert result["data"][CONF_BRIDGE_URL] == "http://bridge:18780"
        assert result["data"][CONF_DEFAULT_AGENT] == "cora"

    @pytest.mark.asyncio
    async def test_step_agents_voice_defaults_to_default(self):
        flow = AgentBridgeConfigFlow()
        flow.hass = MagicMock()
        flow._bridge_url = "http://bridge:18780"
        flow._bridge_token = "tok"
        flow._agents = [{"id": "cora", "name": "Cora"}]

        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()

        result = await flow.async_step_agents({CONF_DEFAULT_AGENT: "cora"})
        assert result["data"][CONF_VOICE_AGENT] == "cora"


class TestOptionsFlow:

    @pytest.mark.asyncio
    async def test_shows_form(self):
        entry = MagicMock()
        entry.options = {}
        flow = AgentBridgeOptionsFlow(entry)
        flow.hass = MagicMock()

        result = await flow.async_step_init()
        assert result["type"] == "form"

    @pytest.mark.asyncio
    async def test_saves_options(self):
        entry = MagicMock()
        entry.options = {}
        flow = AgentBridgeOptionsFlow(entry)
        flow.hass = MagicMock()

        result = await flow.async_step_init(
            {"context_max_chars": 20000, "enable_tool_calls": False}
        )
        assert result["type"] == "create_entry"
