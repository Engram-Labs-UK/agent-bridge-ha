"""Tests for HA service handlers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.exceptions import ServiceValidationError

from custom_components.agent_bridge.const import CONF_DEFAULT_AGENT, DOMAIN
from custom_components.agent_bridge.services import (
    _get_entry_data,
    async_handle_memory_recall,
    async_handle_memory_record,
    _validate_agent_id,
    async_handle_announce,
    async_handle_ask_with_image,
    async_handle_invoke_tool,
    async_handle_send_message,
)


@pytest.fixture
def mock_hass():
    hass = MagicMock()
    coordinator = MagicMock()
    coordinator.data = {
        "agents": [
            {"id": "cora"},
            {"id": "claude"},
        ]
    }
    client = MagicMock()
    client.chat = AsyncMock(
        return_value={
            "choices": [{"message": {"content": "response text"}}],
            "agent": "cora",
            "model": "test-model",
        }
    )
    client.invoke_tool = AsyncMock(return_value={"result": "ok"})

    hass.config_entries.async_entries.return_value = []
    hass.data = {
        DOMAIN: {
            "entry_1": {
                "client": client,
                "coordinator": coordinator,
            }
        }
    }
    return hass


class TestGetEntryData:
    def test_returns_first_entry(self, mock_hass):
        data = _get_entry_data(mock_hass)
        assert "client" in data
        assert "coordinator" in data

    def test_raises_when_no_entries(self):
        hass = MagicMock()
        hass.data = {DOMAIN: {}}
        with pytest.raises(ServiceValidationError, match="not configured"):
            _get_entry_data(hass)

    def test_raises_when_no_domain(self):
        hass = MagicMock()
        hass.data = {}
        with pytest.raises(ServiceValidationError, match="not configured"):
            _get_entry_data(hass)


class TestAskWithImage:
    @pytest.mark.asyncio
    async def test_success_sends_attachment(self, mock_hass):
        call = MagicMock()
        call.hass = mock_hass
        call.data = {
            "message": "Who is at the door?",
            "camera_entity_id": "camera.front_door",
            "agent_id": "cora",
        }

        image = MagicMock(content=b"\x89PNGdata", content_type="image/png")
        with patch(
            "homeassistant.components.camera.async_get_image",
            AsyncMock(return_value=image),
        ):
            result = await async_handle_ask_with_image(call)

        assert result["response"] == "response text"
        client = _get_entry_data(mock_hass)["client"]
        attachments = client.chat.call_args.kwargs["attachments"]
        assert attachments[0]["mime_type"] == "image/png"
        assert attachments[0]["base64"]  # non-empty base64

    @pytest.mark.asyncio
    async def test_defaults_to_configured_agent(self, mock_hass):
        """CR-0016 Item 1: same default-agent fallback as send_message."""
        mock_hass.config_entries.async_entries.return_value = [
            MagicMock(data={CONF_DEFAULT_AGENT: "cora"})
        ]
        call = MagicMock()
        call.hass = mock_hass
        call.data = {"message": "look", "camera_entity_id": "camera.front_door"}

        image = MagicMock(content=b"x", content_type="image/jpeg")
        with patch(
            "homeassistant.components.camera.async_get_image",
            AsyncMock(return_value=image),
        ):
            await async_handle_ask_with_image(call)

        client = _get_entry_data(mock_hass)["client"]
        assert client.chat.call_args.kwargs["agent"] == "cora"

    @pytest.mark.asyncio
    async def test_camera_error_returns_error(self, mock_hass):
        from homeassistant.exceptions import HomeAssistantError

        call = MagicMock()
        call.hass = mock_hass
        call.data = {
            "message": "look",
            "camera_entity_id": "camera.broken",
        }
        with patch(
            "homeassistant.components.camera.async_get_image",
            AsyncMock(side_effect=HomeAssistantError("offline")),
        ):
            result = await async_handle_ask_with_image(call)

        assert result["response"] == ""
        assert "Could not capture" in result["error"]


class TestAnnounce:
    @pytest.mark.asyncio
    async def test_announces_to_available_satellite(self, mock_hass):
        mock_hass.states.get.return_value = MagicMock(state="idle")
        mock_hass.services.async_call = AsyncMock()
        call = MagicMock()
        call.hass = mock_hass
        call.data = {"message": "Washing done", "target": "assist_satellite.kitchen"}

        result = await async_handle_announce(call)
        assert result["announced"] is True
        mock_hass.services.async_call.assert_awaited_once()
        args = mock_hass.services.async_call.await_args.args
        assert args[0] == "assist_satellite" and args[1] == "announce"

    @pytest.mark.asyncio
    async def test_skips_unavailable_when_not_critical(self, mock_hass):
        mock_hass.states.get.return_value = MagicMock(state="unavailable")
        mock_hass.services.async_call = AsyncMock()
        call = MagicMock()
        call.hass = mock_hass
        call.data = {
            "message": "Bin day",
            "target": "assist_satellite.bedroom",
            "priority": "low",
        }

        result = await async_handle_announce(call)
        assert result["announced"] is False
        assert "unavailable" in result["reason"]
        mock_hass.services.async_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_critical_announces_even_if_unavailable(self, mock_hass):
        mock_hass.states.get.return_value = MagicMock(state="unavailable")
        mock_hass.services.async_call = AsyncMock()
        call = MagicMock()
        call.hass = mock_hass
        call.data = {
            "message": "Smoke detected",
            "target": "assist_satellite.hall",
            "priority": "critical",
        }

        result = await async_handle_announce(call)
        assert result["announced"] is True
        mock_hass.services.async_call.assert_awaited_once()


class TestValidateAgentId:
    def test_valid_agent(self, mock_hass):
        data = _get_entry_data(mock_hass)
        # Should not raise
        _validate_agent_id(data["coordinator"], "cora")

    def test_unknown_agent(self, mock_hass):
        data = _get_entry_data(mock_hass)
        with pytest.raises(ServiceValidationError, match="Unknown agent"):
            _validate_agent_id(data["coordinator"], "nonexistent")

    def test_no_data(self):
        coordinator = MagicMock()
        coordinator.data = None
        with pytest.raises(ServiceValidationError, match="not available"):
            _validate_agent_id(coordinator, "cora")


class TestSendMessage:
    @pytest.mark.asyncio
    async def test_success(self, mock_hass):
        call = MagicMock()
        call.hass = mock_hass
        call.data = {"message": "Hello", "agent_id": "cora"}

        result = await async_handle_send_message(call)
        assert result["response"] == "response text"
        assert result["agent_id"] == "cora"

    @pytest.mark.asyncio
    async def test_without_agent_id(self, mock_hass):
        call = MagicMock()
        call.hass = mock_hass
        call.data = {"message": "Hello"}

        result = await async_handle_send_message(call)
        assert "response" in result

    @pytest.mark.asyncio
    async def test_defaults_to_configured_agent(self, mock_hass):
        """CR-0016 Item 1: agent_id omitted -> the configured default agent
        (the behaviour services.yaml has documented all along)."""
        mock_hass.config_entries.async_entries.return_value = [
            MagicMock(data={CONF_DEFAULT_AGENT: "cora"})
        ]
        call = MagicMock()
        call.hass = mock_hass
        call.data = {"message": "Hello"}

        await async_handle_send_message(call)
        client = _get_entry_data(mock_hass)["client"]
        assert client.chat.call_args.kwargs["agent"] == "cora"

    @pytest.mark.asyncio
    async def test_no_default_falls_back_to_bridge_routing(self, mock_hass):
        """CR-0016 Item 1: no default configured -> agent=None (bridge routes)."""
        call = MagicMock()
        call.hass = mock_hass
        call.data = {"message": "Hello"}

        await async_handle_send_message(call)
        client = _get_entry_data(mock_hass)["client"]
        assert client.chat.call_args.kwargs["agent"] is None

    @pytest.mark.asyncio
    async def test_bridge_error(self, mock_hass):
        from custom_components.agent_bridge.client import BridgeError

        data = _get_entry_data(mock_hass)
        data["client"].chat = AsyncMock(side_effect=BridgeError("TIMEOUT", "timed out"))

        call = MagicMock()
        call.hass = mock_hass
        call.data = {"message": "Hello"}

        result = await async_handle_send_message(call)
        assert "error" in result


class TestInvokeTool:
    @pytest.mark.asyncio
    async def test_success(self, mock_hass):
        call = MagicMock()
        call.hass = mock_hass
        call.data = {
            "agent_id": "cora",
            "tool_name": "web_search",
            "args": {"q": "test"},
        }

        result = await async_handle_invoke_tool(call)
        assert result["agent_id"] == "cora"

    @pytest.mark.asyncio
    async def test_unknown_agent(self, mock_hass):
        call = MagicMock()
        call.hass = mock_hass
        call.data = {
            "agent_id": "nonexistent",
            "tool_name": "web_search",
        }

        with pytest.raises(ServiceValidationError, match="Unknown agent"):
            await async_handle_invoke_tool(call)


class TestMemoryServices:
    """CR-0010: memory_record / memory_recall services."""

    @pytest.mark.asyncio
    async def test_record_with_explicit_agent(self, mock_hass):
        client = _get_entry_data(mock_hass)["client"]
        client.memory_record = AsyncMock(return_value={})
        call = MagicMock()
        call.hass = mock_hass
        call.data = {"content": "the back door sticks", "agent_id": "cora", "tags": ["home"]}

        result = await async_handle_memory_record(call)
        assert result == {"recorded": True, "agent_id": "cora"}
        client.memory_record.assert_awaited_once_with(
            "cora", "the back door sticks", tags=["home"]
        )

    @pytest.mark.asyncio
    async def test_record_defaults_to_configured_agent(self, mock_hass):
        client = _get_entry_data(mock_hass)["client"]
        client.memory_record = AsyncMock(return_value={})
        mock_hass.config_entries.async_entries.return_value = [
            MagicMock(data={CONF_DEFAULT_AGENT: "cora"})
        ]
        call = MagicMock()
        call.hass = mock_hass
        call.data = {"content": "bins go out Tuesday"}

        result = await async_handle_memory_record(call)
        assert result["recorded"] is True
        assert result["agent_id"] == "cora"

    @pytest.mark.asyncio
    async def test_recall_normalises_items(self, mock_hass):
        client = _get_entry_data(mock_hass)["client"]
        client.memory_recall = AsyncMock(
            return_value={"agent": "cora", "items": [{"content": "x"}]}
        )
        call = MagicMock()
        call.hass = mock_hass
        call.data = {"agent_id": "cora", "query": "door"}

        result = await async_handle_memory_recall(call)
        assert result["agent_id"] == "cora"
        assert result["items"] == [{"content": "x"}]
        client.memory_recall.assert_awaited_once_with("cora", query="door")

    @pytest.mark.asyncio
    async def test_recall_handles_untyped_response(self, mock_hass):
        client = _get_entry_data(mock_hass)["client"]
        client.memory_recall = AsyncMock(return_value={})  # no items key
        call = MagicMock()
        call.hass = mock_hass
        call.data = {"agent_id": "cora"}

        result = await async_handle_memory_recall(call)
        assert result["items"] == []

    @pytest.mark.asyncio
    async def test_record_rejects_unknown_agent(self, mock_hass):
        call = MagicMock()
        call.hass = mock_hass
        call.data = {"content": "x", "agent_id": "ghost"}
        with pytest.raises(ServiceValidationError, match="Unknown agent"):
            await async_handle_memory_record(call)
