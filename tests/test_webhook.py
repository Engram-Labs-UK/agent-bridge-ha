"""Tests for webhook integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.agent_bridge.webhook import (
    async_register_webhook,
    async_register_with_bridge,
    async_unregister_webhook,
    _handle_webhook,
)
from custom_components.agent_bridge.const import DOMAIN


class TestAsyncRegisterWebhook:

    @pytest.mark.asyncio
    async def test_registers_with_ha(self):
        hass = MagicMock()

        with patch(
            "custom_components.agent_bridge.webhook.webhook.async_generate_id",
            return_value="wh_test_123",
        ), patch(
            "custom_components.agent_bridge.webhook.webhook.async_register",
        ) as mock_register:
            result = await async_register_webhook(hass, "entry_1")

        assert result == "wh_test_123"
        mock_register.assert_called_once()


class TestAsyncRegisterWithBridge:

    @pytest.mark.asyncio
    async def test_success(self):
        hass = MagicMock()
        client = MagicMock()
        client.register_webhook = AsyncMock(return_value={"id": "sub_123"})

        hass.data = {DOMAIN: {"entry_1": {"client": client}}}

        with patch(
            "homeassistant.helpers.network.get_url",
            return_value="http://ha.local:8123",
        ):
            result = await async_register_with_bridge(hass, "entry_1", "wh_123")

        assert result == "sub_123"
        # US0024/AC2: subscribe to the full v4.36 catalogue, not just one event.
        call_url, call_events = client.register_webhook.call_args[0]
        assert call_url == "http://ha.local:8123/api/webhook/wh_123"
        assert set(call_events) >= {
            "agent:registered",
            "agent:unregistered",
            "agent:updated",
            "agent:health-changed",
            "message:error",
            "bridge:upgraded",
        }

    @pytest.mark.asyncio
    async def test_no_ha_url(self):
        hass = MagicMock()
        client = MagicMock()
        hass.data = {DOMAIN: {"entry_1": {"client": client}}}

        with patch(
            "homeassistant.helpers.network.get_url",
            side_effect=RuntimeError("no url"),
        ):
            result = await async_register_with_bridge(hass, "entry_1", "wh_123")

        assert result is None

    @pytest.mark.asyncio
    async def test_bridge_registration_fails(self):
        hass = MagicMock()
        client = MagicMock()
        client.register_webhook = AsyncMock(side_effect=RuntimeError("fail"))
        hass.data = {DOMAIN: {"entry_1": {"client": client}}}

        with patch(
            "homeassistant.helpers.network.get_url",
            return_value="http://ha.local:8123",
        ):
            result = await async_register_with_bridge(hass, "entry_1", "wh_123")

        assert result is None

    @pytest.mark.asyncio
    async def test_no_client(self):
        hass = MagicMock()
        hass.data = {DOMAIN: {"entry_1": {}}}

        result = await async_register_with_bridge(hass, "entry_1", "wh_123")
        assert result is None


class TestAsyncUnregisterWebhook:

    @pytest.mark.asyncio
    async def test_unregisters_both(self):
        hass = MagicMock()
        client = MagicMock()
        client.unregister_webhook = AsyncMock()
        hass.data = {DOMAIN: {"entry_1": {"client": client}}}

        with patch(
            "custom_components.agent_bridge.webhook.webhook.async_unregister"
        ) as mock_ha_unreg:
            await async_unregister_webhook(hass, "entry_1", "wh_123", "sub_123")

        client.unregister_webhook.assert_called_once_with("sub_123")
        mock_ha_unreg.assert_called_once_with(hass, "wh_123")

    @pytest.mark.asyncio
    async def test_no_subscription_id(self):
        hass = MagicMock()

        with patch(
            "custom_components.agent_bridge.webhook.webhook.async_unregister"
        ) as mock_ha_unreg:
            await async_unregister_webhook(hass, "entry_1", "wh_123", None)

        mock_ha_unreg.assert_called_once_with(hass, "wh_123")

    @pytest.mark.asyncio
    async def test_no_webhook_id(self):
        hass = MagicMock()

        with patch(
            "custom_components.agent_bridge.webhook.webhook.async_unregister"
        ) as mock_ha_unreg:
            await async_unregister_webhook(hass, "entry_1", None, None)

        mock_ha_unreg.assert_not_called()

    @pytest.mark.asyncio
    async def test_bridge_unregister_fails_gracefully(self):
        hass = MagicMock()
        client = MagicMock()
        client.unregister_webhook = AsyncMock(side_effect=RuntimeError("fail"))
        hass.data = {DOMAIN: {"entry_1": {"client": client}}}

        with patch(
            "custom_components.agent_bridge.webhook.webhook.async_unregister"
        ):
            # Should not raise
            await async_unregister_webhook(hass, "entry_1", "wh_123", "sub_123")


class TestHandleWebhook:

    @pytest.mark.asyncio
    async def test_health_changed_event(self):
        hass = MagicMock()
        coordinator = MagicMock()
        coordinator.async_push_webhook_data = AsyncMock()
        hass.data = {DOMAIN: {"entry_1": {"coordinator": coordinator}}}

        request = MagicMock()
        request.json = AsyncMock(
            return_value={
                "event": "agent:health-changed",
                "data": {"status": "degraded"},
            }
        )

        response = await _handle_webhook(hass, "wh_123", request)

        assert response.status == 200
        coordinator.async_push_webhook_data.assert_called_once_with(
            {"status": "degraded"}
        )

    @pytest.mark.asyncio
    async def test_unknown_event_type(self):
        hass = MagicMock()
        hass.data = {DOMAIN: {}}

        request = MagicMock()
        request.json = AsyncMock(
            return_value={"event": "unknown:event", "data": {}}
        )

        response = await _handle_webhook(hass, "wh_123", request)
        assert response.status == 200

    @pytest.mark.asyncio
    async def test_invalid_payload(self):
        hass = MagicMock()

        request = MagicMock()
        request.json = AsyncMock(side_effect=ValueError("bad json"))

        response = await _handle_webhook(hass, "wh_123", request)
        assert response.status == 400

    @pytest.mark.asyncio
    @pytest.mark.parametrize("payload", [[1, 2, 3], "x", 42, None, True])
    async def test_non_object_json_payload_is_400(self, payload):
        """BG0014: valid JSON that is not an object gets the same clean 400 as
        unparseable JSON -- never an unhandled AttributeError."""
        hass = MagicMock()
        hass.data = {DOMAIN: {}}

        request = MagicMock()
        request.json = AsyncMock(return_value=payload)

        response = await _handle_webhook(hass, "wh_123", request)
        assert response.status == 400

    @pytest.mark.asyncio
    async def test_coordinator_push(self):
        """Test that async_push_webhook_data updates coordinator state."""
        from custom_components.agent_bridge.coordinator import (
            AgentBridgeCoordinator,
            CoordinatorData,
        )

        hass = MagicMock()
        client = MagicMock()
        coord = AgentBridgeCoordinator(hass, client)

        # Set initial data
        coord.data = CoordinatorData(
            connected=True,
            bridge_status="ok",
            bridge_version="3.2.0",
            bridge_uptime=1000,
            agent_count_healthy=3,
            agent_count_total=3,
            agents=[],
            last_poll="2026-04-05T00:00:00Z",
        )

        coord.async_set_updated_data = MagicMock()
        await coord.async_push_webhook_data({"status": "degraded"})

        coord.async_set_updated_data.assert_called_once()
        updated = coord.async_set_updated_data.call_args[0][0]
        assert updated["bridge_status"] == "degraded"

    @pytest.mark.asyncio
    async def test_push_no_data(self):
        from custom_components.agent_bridge.coordinator import AgentBridgeCoordinator

        hass = MagicMock()
        client = MagicMock()
        coord = AgentBridgeCoordinator(hass, client)
        coord.data = None
        coord.async_set_updated_data = MagicMock()

        # Should not crash or call update
        await coord.async_push_webhook_data({"status": "ok"})
        coord.async_set_updated_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_bridge_upgraded_fires_ha_event(self):
        """US0024/AC3: bridge:upgraded routes to an HA event for drift detection."""
        from custom_components.agent_bridge.const import EVENT_BRIDGE_UPGRADED

        hass = MagicMock()
        hass.bus.async_fire = MagicMock()
        hass.data = {DOMAIN: {}}

        request = MagicMock()
        request.json = AsyncMock(
            return_value={
                "event": "bridge:upgraded",
                "data": {"version": "4.37.0", "previous": "4.36.0"},
            }
        )

        response = await _handle_webhook(hass, "wh_123", request)

        assert response.status == 200
        hass.bus.async_fire.assert_called_once_with(
            EVENT_BRIDGE_UPGRADED, {"version": "4.37.0", "previous": "4.36.0"}
        )

    @pytest.mark.asyncio
    async def test_roster_event_triggers_refresh(self):
        """agent:registered should pull a fresh discovery, not wait on the poll."""
        hass = MagicMock()
        coordinator = MagicMock()
        coordinator.async_request_refresh = AsyncMock()
        hass.data = {DOMAIN: {"entry_1": {"coordinator": coordinator}}}

        request = MagicMock()
        request.json = AsyncMock(
            return_value={"event": "agent:registered", "data": {"agentId": "eve"}}
        )

        await _handle_webhook(hass, "wh_123", request)
        coordinator.async_request_refresh.assert_called_once()


class TestPerAgentHealthPush:
    """US0024/AC1: {agentId, healthy} updates that agent's flag + healthy count."""

    @pytest.mark.asyncio
    async def test_agent_health_changed_updates_state(self):
        from custom_components.agent_bridge.coordinator import (
            AgentBridgeCoordinator,
            CoordinatorData,
        )

        hass = MagicMock()
        coord = AgentBridgeCoordinator(hass, MagicMock())
        coord.data = CoordinatorData(
            connected=True,
            bridge_status="ok",
            bridge_version="4.36.0",
            bridge_uptime=1000,
            agent_count_healthy=2,
            agent_count_total=2,
            agents=[
                {"id": "cora", "name": "Cora", "description": "", "healthy": True,
                 "adapter": "", "capabilities": {}, "tags": []},
                {"id": "eve", "name": "Eve", "description": "", "healthy": True,
                 "adapter": "", "capabilities": {}, "tags": []},
            ],
            last_poll="2026-04-05T00:00:00Z",
        )
        coord.async_set_updated_data = MagicMock()

        await coord.async_push_webhook_data({"agentId": "eve", "healthy": False})

        coord.async_set_updated_data.assert_called_once()
        updated = coord.async_set_updated_data.call_args[0][0]
        eve = next(a for a in updated["agents"] if a["id"] == "eve")
        assert eve["healthy"] is False
        assert updated["agent_count_healthy"] == 1

    @pytest.mark.asyncio
    async def test_unknown_agent_requests_refresh(self):
        from custom_components.agent_bridge.coordinator import (
            AgentBridgeCoordinator,
            CoordinatorData,
        )

        hass = MagicMock()
        coord = AgentBridgeCoordinator(hass, MagicMock())
        coord.data = CoordinatorData(
            connected=True, bridge_status="ok", bridge_version="4.36.0",
            bridge_uptime=1, agent_count_healthy=0, agent_count_total=0,
            agents=[], last_poll="2026-04-05T00:00:00Z",
        )
        coord.async_set_updated_data = MagicMock()
        coord.async_request_refresh = AsyncMock()

        await coord.async_push_webhook_data({"agentId": "ghost", "healthy": False})

        coord.async_set_updated_data.assert_not_called()
        coord.async_request_refresh.assert_called_once()
