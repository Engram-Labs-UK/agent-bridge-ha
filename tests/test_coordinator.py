"""Tests for the DataUpdateCoordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.agent_bridge.client import BridgeConnectionError
from custom_components.agent_bridge.coordinator import (
    AgentBridgeCoordinator,
    AgentInfo,
    CoordinatorData,
)

from .conftest import DISCOVERY_THREE_AGENTS, HEALTH_SHALLOW_OK


@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.bus.async_fire = MagicMock()
    return hass


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.health = AsyncMock(return_value=HEALTH_SHALLOW_OK)
    client.discover = AsyncMock(return_value=DISCOVERY_THREE_AGENTS)
    return client


@pytest.fixture
def coordinator(mock_hass, mock_client):
    coord = AgentBridgeCoordinator(
        mock_hass, mock_client, poll_interval=30, discovery_interval=300
    )
    return coord


class TestParseAgent:

    def test_parses_healthy_agent(self, coordinator):
        raw = {
            "id": "cora",
            "name": "Cora",
            "description": "Primary",
            "status": "healthy",
            "adapter": "http-openai",
            "capabilities": {"chat": True},
            "tags": ["primary"],
        }
        info = coordinator._parse_agent(raw)
        assert info["id"] == "cora"
        assert info["healthy"] is True
        assert info["adapter"] == "http-openai"

    def test_parses_unhealthy_agent(self, coordinator):
        raw = {"id": "prof", "status": "unhealthy"}
        info = coordinator._parse_agent(raw)
        assert info["healthy"] is False

    def test_missing_fields_default(self, coordinator):
        raw = {}
        info = coordinator._parse_agent(raw)
        assert info["id"] == ""
        assert info["name"] == ""
        assert info["healthy"] is False


class TestAsyncUpdateData:

    @pytest.mark.asyncio
    async def test_successful_poll(self, coordinator, mock_client):
        # Force discovery by setting last_discovery to 0
        coordinator._last_discovery = 0
        data = await coordinator._async_update_data()
        assert data["connected"] is True
        assert data["bridge_status"] == "ok"
        assert data["agent_count_healthy"] == 3
        assert data["agent_count_total"] == 3
        assert len(data["agents"]) == 3

    @pytest.mark.asyncio
    async def test_cache_on_first_failure(self, coordinator, mock_client):
        # First successful poll
        coordinator._last_discovery = 0
        good_data = await coordinator._async_update_data()
        assert good_data["connected"] is True

        # Now fail
        mock_client.health = AsyncMock(
            side_effect=BridgeConnectionError("offline")
        )
        data = await coordinator._async_update_data()
        # Should use cached data (failure 1 of 3)
        assert data["connected"] is True
        assert coordinator._consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_disconnected_after_3_failures(self, coordinator, mock_client):
        mock_client.health = AsyncMock(
            side_effect=BridgeConnectionError("offline")
        )
        # No cached data
        coordinator._last_good_data = None

        data = await coordinator._async_update_data()
        assert data["connected"] is False
        assert data["bridge_status"] == "error"

    @pytest.mark.asyncio
    async def test_cache_survives_3_failures(self, coordinator, mock_client):
        # First successful poll
        coordinator._last_discovery = 0
        await coordinator._async_update_data()

        # Fail 3 times
        mock_client.health = AsyncMock(
            side_effect=BridgeConnectionError("offline")
        )
        for _ in range(3):
            data = await coordinator._async_update_data()
            assert data["connected"] is True  # still using cache

        # 4th failure: no more cache
        data = await coordinator._async_update_data()
        assert data["connected"] is False

    @pytest.mark.asyncio
    async def test_recovery_resets_failures(self, coordinator, mock_client):
        coordinator._last_discovery = 0
        await coordinator._async_update_data()

        # Fail once
        mock_client.health = AsyncMock(
            side_effect=BridgeConnectionError("offline")
        )
        await coordinator._async_update_data()
        assert coordinator._consecutive_failures == 1

        # Recover
        mock_client.health = AsyncMock(return_value=HEALTH_SHALLOW_OK)
        await coordinator._async_update_data()
        assert coordinator._consecutive_failures == 0


class TestAgentDiffDetection:

    @pytest.mark.asyncio
    async def test_new_agent_fires_event(self, coordinator, mock_client, mock_hass):
        coordinator._last_discovery = 0
        coordinator._previous_agents = []
        await coordinator._async_update_data()

        # Should fire agent_discovered for all 3 agents
        calls = mock_hass.bus.async_fire.call_args_list
        discovered = [c for c in calls if c[0][0] == "agent_bridge_agent_discovered"]
        assert len(discovered) == 3

    @pytest.mark.asyncio
    async def test_removed_agent_fires_event(self, coordinator, mock_client, mock_hass):
        coordinator._last_discovery = 0
        coordinator._previous_agents = [
            AgentInfo(
                id="old_agent", name="Old", description="", healthy=True,
                adapter="", capabilities={}, tags=[]
            ),
            *[coordinator._parse_agent(a) for a in DISCOVERY_THREE_AGENTS],
        ]

        await coordinator._async_update_data()
        calls = mock_hass.bus.async_fire.call_args_list
        removed = [c for c in calls if c[0][0] == "agent_bridge_agent_removed"]
        assert len(removed) == 1
        assert removed[0][0][1]["agent_id"] == "old_agent"

    @pytest.mark.asyncio
    async def test_discovery_interval_respected(self, coordinator, mock_client):
        import time
        # Set last discovery to now so it skips
        coordinator._last_discovery = time.monotonic()
        coordinator._previous_agents = [
            coordinator._parse_agent(a) for a in DISCOVERY_THREE_AGENTS
        ]
        await coordinator._async_update_data()
        # discover should NOT be called since interval hasn't passed
        mock_client.discover.assert_not_called()
