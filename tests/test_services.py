"""Tests for HA service handlers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.agent_bridge.const import DOMAIN
from custom_components.agent_bridge.services import (
    _get_entry_data,
    _validate_agent_id,
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
        with pytest.raises(ValueError, match="not configured"):
            _get_entry_data(hass)

    def test_raises_when_no_domain(self):
        hass = MagicMock()
        hass.data = {}
        with pytest.raises(ValueError, match="not configured"):
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


class TestValidateAgentId:
    def test_valid_agent(self, mock_hass):
        data = _get_entry_data(mock_hass)
        # Should not raise
        _validate_agent_id(data["coordinator"], "cora")

    def test_unknown_agent(self, mock_hass):
        data = _get_entry_data(mock_hass)
        with pytest.raises(ValueError, match="Unknown agent"):
            _validate_agent_id(data["coordinator"], "nonexistent")

    def test_no_data(self):
        coordinator = MagicMock()
        coordinator.data = None
        with pytest.raises(ValueError, match="not available"):
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

        with pytest.raises(ValueError, match="Unknown agent"):
            await async_handle_invoke_tool(call)
