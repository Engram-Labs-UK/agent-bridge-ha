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
        # BG0009: the first-run picker requests crew so labels read "name (crew)".
        instance.discover.assert_awaited_with(include=["crew"])

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


class TestSetupSslVerify:
    """CR-0016 Item 4: self-signed bridges can onboard -- SSL verify is a
    first-run choice (default on), stored into the created entry's options."""

    @pytest.mark.asyncio
    async def test_user_step_ssl_verify_disabled(self):
        flow = AgentBridgeConfigFlow()
        flow.hass = MagicMock()

        with patch(
            "custom_components.agent_bridge.config_flow.async_get_clientsession"
        ), patch(
            "custom_components.agent_bridge.config_flow.BridgeClient"
        ) as MockClient:
            instance = MockClient.return_value
            instance.check_alive = AsyncMock(return_value=True)
            instance.discover = AsyncMock(return_value=[{"id": "cora", "name": "Cora"}])

            result = await flow.async_step_user(
                {
                    CONF_BRIDGE_URL: "https://bridge:18780",
                    CONF_BRIDGE_TOKEN: "tok",
                    "ssl_verify": False,
                }
            )
        assert result["step_id"] == "agents"
        assert MockClient.call_args.kwargs.get("ssl_verify") is False

        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()
        result = await flow.async_step_agents({CONF_DEFAULT_AGENT: "cora"})
        assert result["options"]["ssl_verify"] is False

    @pytest.mark.asyncio
    async def test_user_step_ssl_verify_defaults_on(self):
        flow = AgentBridgeConfigFlow()
        flow.hass = MagicMock()

        with patch(
            "custom_components.agent_bridge.config_flow.async_get_clientsession"
        ), patch(
            "custom_components.agent_bridge.config_flow.BridgeClient"
        ) as MockClient:
            instance = MockClient.return_value
            instance.check_alive = AsyncMock(return_value=True)
            instance.discover = AsyncMock(return_value=[{"id": "cora", "name": "Cora"}])

            await flow.async_step_user(
                {CONF_BRIDGE_URL: "http://bridge:18780", CONF_BRIDGE_TOKEN: "tok"}
            )
        assert MockClient.call_args.kwargs.get("ssl_verify") is True


class TestOptionsFlow:

    @pytest.mark.asyncio
    async def test_agent_options_discovery_sends_caller_id(self):
        """BG0015: the options-flow discovery client must carry the caller header
        (BG0004 parity with the subentry flow's _discover_agents)."""
        entry = MagicMock()
        entry.data = {
            CONF_BRIDGE_URL: "http://bridge:18780",
            CONF_BRIDGE_TOKEN: "tok",
            CONF_DEFAULT_AGENT: "openclaw-openclaw-cora",
        }
        entry.options = {}
        flow = AgentBridgeOptionsFlow(entry)
        flow.hass = MagicMock()

        with patch(
            "custom_components.agent_bridge.config_flow.async_get_clientsession"
        ), patch(
            "custom_components.agent_bridge.config_flow.BridgeClient"
        ) as MockClient:
            instance = MockClient.return_value
            instance.discover = AsyncMock(return_value=[{"id": "cora", "name": "Cora"}])
            options = await flow._get_agent_options()

        assert options == {"cora": "Cora"}
        assert MockClient.call_args.kwargs.get("caller_id") == "openclaw-openclaw-cora"

    @pytest.mark.asyncio
    async def test_shows_form(self):
        entry = MagicMock()
        entry.options = {}
        flow = AgentBridgeOptionsFlow(entry)
        flow.hass = MagicMock()

        # Stub agent discovery so the options flow never opens a real aiohttp
        # connector (a MagicMock hass would otherwise leak a lingering timer).
        with patch.object(
            AgentBridgeOptionsFlow, "_get_agent_options",
            AsyncMock(return_value={"cora": "Cora (healthy)"}),
        ):
            result = await flow.async_step_init()
        assert result["type"] == "form"

    @pytest.mark.asyncio
    async def test_saves_options_flattens_advanced(self):
        # CR-0007: the Advanced section is flattened back to a flat options dict,
        # and the agent selection is moved to entry.data (not options).
        entry = MagicMock()
        entry.options = {}
        entry.data = {}
        flow = AgentBridgeOptionsFlow(entry)
        flow.hass = MagicMock()

        with patch.object(
            AgentBridgeOptionsFlow, "_get_agent_options",
            AsyncMock(return_value={"cora": "Cora (deskpoint)"}),
        ):
            result = await flow.async_step_init(
                {
                    "default_agent": "cora",
                    "ssl_verify": True,
                    "advanced": {"context_max_chars": 20000, "thinking_timeout": 90},
                }
            )
        assert result["type"] == "create_entry"
        data = result["data"]
        # advanced fields flattened to the top level
        assert data["context_max_chars"] == 20000
        assert data["thinking_timeout"] == 90
        assert data["ssl_verify"] is True
        # the section wrapper and the agent key never leak into stored options
        assert "advanced" not in data
        assert "default_agent" not in data

    @pytest.mark.asyncio
    async def test_session_window_coerced_to_int(self):
        # CR-0013: the session-continuity dropdown yields a string; it must be stored
        # as an int so conversation.py keeps reading a number.
        entry = MagicMock()
        entry.options = {}
        entry.data = {}
        flow = AgentBridgeOptionsFlow(entry)
        flow.hass = MagicMock()

        with patch.object(
            AgentBridgeOptionsFlow, "_get_agent_options",
            AsyncMock(return_value={"cora": "Cora"}),
        ):
            result = await flow.async_step_init(
                {
                    "default_agent": "cora",
                    "ssl_verify": True,
                    "advanced": {"session_idle_window": "1800", "doctor_alerts": True},
                }
            )
        assert result["data"]["session_idle_window"] == 1800
        assert isinstance(result["data"]["session_idle_window"], int)
        assert result["data"]["doctor_alerts"] is True


class TestOptionsTranslations:
    """CR-0007: every option field has a human label and the two files agree."""

    @staticmethod
    def _load(name):
        import json
        import pathlib

        base = pathlib.Path("custom_components/agent_bridge")
        return json.loads((base / name).read_text())

    def test_strings_and_en_parity(self):
        assert self._load("strings.json")["options"] == self._load("translations/en.json")["options"]

    def test_every_option_field_has_a_label(self):
        init = self._load("strings.json")["options"]["step"]["init"]
        labels = set(init["data"]) | set(init["sections"]["advanced"]["data"])
        expected = {
            "default_agent",
            "ssl_verify",
            "context_max_chars",
            "thinking_timeout",
            "session_idle_window",
            "enable_streaming",
            "doctor_alerts",
        }
        assert expected <= labels
        # CR-0013 removed these
        assert "caller_id" not in labels
        assert "debug_logging" not in labels
