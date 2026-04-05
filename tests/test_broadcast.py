"""Tests for broadcast service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.agent_bridge.services import (
    async_handle_broadcast,
    BROADCAST_SCHEMA,
)
from custom_components.agent_bridge.client import BridgeError
from custom_components.agent_bridge.const import DOMAIN


@pytest.fixture
def mock_hass():
    hass = MagicMock()
    client = MagicMock()
    client.broadcast = AsyncMock(
        return_value={
            "responses": [
                {"agent": "cora", "content": "Acknowledged."},
                {"agent": "claude", "content": "Understood."},
            ]
        }
    )
    coordinator = MagicMock()
    coordinator.data = {"agents": [{"id": "cora"}, {"id": "claude"}]}

    hass.data = {
        DOMAIN: {
            "entry_1": {
                "client": client,
                "coordinator": coordinator,
            }
        }
    }
    return hass


class TestBroadcastSchema:

    def test_valid_with_message(self):
        result = BROADCAST_SCHEMA({"message": "Hello all"})
        assert result["message"] == "Hello all"

    def test_valid_with_tags(self):
        result = BROADCAST_SCHEMA({"message": "Hello", "tags": ["primary"]})
        assert result["tags"] == ["primary"]

    def test_missing_message_raises(self):
        import voluptuous
        with pytest.raises(voluptuous.error.MultipleInvalid):
            BROADCAST_SCHEMA({})


class TestBroadcastService:

    @pytest.mark.asyncio
    async def test_success(self, mock_hass):
        call = MagicMock()
        call.hass = mock_hass
        call.data = {"message": "Hello all"}

        result = await async_handle_broadcast(call)
        assert len(result["responses"]) == 2
        assert result["responses"][0]["agent"] == "cora"

    @pytest.mark.asyncio
    async def test_with_tags(self, mock_hass):
        call = MagicMock()
        call.hass = mock_hass
        call.data = {"message": "Hello", "tags": ["primary"]}

        await async_handle_broadcast(call)

        client = mock_hass.data[DOMAIN]["entry_1"]["client"]
        client.broadcast.assert_called_once_with("Hello", tags=["primary"])

    @pytest.mark.asyncio
    async def test_bridge_error(self, mock_hass):
        client = mock_hass.data[DOMAIN]["entry_1"]["client"]
        client.broadcast = AsyncMock(
            side_effect=BridgeError("TIMEOUT", "timed out")
        )

        call = MagicMock()
        call.hass = mock_hass
        call.data = {"message": "Hello"}

        result = await async_handle_broadcast(call)
        assert result["responses"] == []
        assert "error" in result

    @pytest.mark.asyncio
    async def test_empty_responses(self, mock_hass):
        client = mock_hass.data[DOMAIN]["entry_1"]["client"]
        client.broadcast = AsyncMock(return_value={})

        call = MagicMock()
        call.hass = mock_hass
        call.data = {"message": "Hello"}

        result = await async_handle_broadcast(call)
        assert result["responses"] == []
