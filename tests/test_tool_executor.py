"""Tests for tool executor -- HA service execution from agent tool_calls."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.agent_bridge.tool_executor import (
    _parse_tool_arguments,
    execute_tool_call,
    _execute_single_service,
)


class TestParseToolArguments:

    def test_dict_passthrough(self):
        assert _parse_tool_arguments({"a": 1}) == {"a": 1}

    def test_json_string(self):
        assert _parse_tool_arguments('{"a": 1}') == {"a": 1}

    def test_invalid_json(self):
        assert _parse_tool_arguments("not json") == {}

    def test_json_non_dict(self):
        assert _parse_tool_arguments("[1, 2, 3]") == {}

    def test_none_input(self):
        assert _parse_tool_arguments(None) == {}

    def test_int_input(self):
        assert _parse_tool_arguments(42) == {}


class TestExecuteSingleService:

    @pytest.mark.asyncio
    async def test_success(self):
        hass = MagicMock()
        hass.services.async_call = AsyncMock()
        result = await _execute_single_service(
            hass, "light", "turn_on", "light.kitchen"
        )
        assert result["success"] is True
        assert result["entity_id"] == "light.kitchen"
        assert result["service"] == "light.turn_on"
        assert "duration_ms" in result

    @pytest.mark.asyncio
    async def test_timeout(self):
        hass = MagicMock()
        hass.services.async_call = AsyncMock(side_effect=TimeoutError)
        result = await _execute_single_service(
            hass, "light", "turn_on", "light.kitchen", timeout=0.01
        )
        assert result["success"] is False
        assert "timed out" in result["error"]

    @pytest.mark.asyncio
    async def test_exception(self):
        hass = MagicMock()
        hass.services.async_call = AsyncMock(side_effect=RuntimeError("boom"))
        result = await _execute_single_service(
            hass, "light", "turn_on", "light.kitchen"
        )
        assert result["success"] is False
        assert "boom" in result["error"]


class TestExecuteToolCall:

    @pytest.mark.asyncio
    async def test_execute_service_valid_entity(self):
        hass = MagicMock()
        hass.services.async_call = AsyncMock()
        hass.bus.async_fire = MagicMock()

        tool_call = {
            "id": "call_1",
            "function": {
                "name": "execute_service",
                "arguments": '{"domain": "light", "service": "turn_on", "entity_id": "light.kitchen"}',
            },
        }
        result = await execute_tool_call(
            hass, tool_call, {"light.kitchen", "light.study"}
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_service_unexposed_entity(self):
        hass = MagicMock()
        hass.bus.async_fire = MagicMock()

        tool_call = {
            "id": "call_1",
            "function": {
                "name": "execute_service",
                "arguments": '{"domain": "light", "service": "turn_on", "entity_id": "light.secret"}',
            },
        }
        result = await execute_tool_call(hass, tool_call, {"light.kitchen"})
        assert result["success"] is False
        assert "not found in exposed" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_service_missing_domain(self):
        hass = MagicMock()

        tool_call = {
            "id": "call_1",
            "function": {
                "name": "execute_service",
                "arguments": '{"service": "turn_on", "entity_id": "light.kitchen"}',
            },
        }
        result = await execute_tool_call(hass, tool_call, {"light.kitchen"})
        assert result["success"] is False
        assert "Missing domain" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_service_missing_entity_id(self):
        hass = MagicMock()

        tool_call = {
            "id": "call_1",
            "function": {
                "name": "execute_service",
                "arguments": '{"domain": "light", "service": "turn_on"}',
            },
        }
        result = await execute_tool_call(hass, tool_call, set())
        assert result["success"] is False
        assert "Missing entity_id" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_service_target_dict(self):
        hass = MagicMock()
        hass.services.async_call = AsyncMock()
        hass.bus.async_fire = MagicMock()

        tool_call = {
            "id": "call_1",
            "function": {
                "name": "execute_service",
                "arguments": '{"domain": "light", "service": "turn_on", "target": {"entity_id": "light.kitchen"}}',
            },
        }
        result = await execute_tool_call(hass, tool_call, {"light.kitchen"})
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        hass = MagicMock()

        tool_call = {
            "id": "call_1",
            "function": {"name": "unknown_tool", "arguments": "{}"},
        }
        result = await execute_tool_call(hass, tool_call, set())
        assert result["success"] is False
        assert "Unknown tool" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_services_batch(self):
        hass = MagicMock()
        hass.services.async_call = AsyncMock()
        hass.bus.async_fire = MagicMock()

        tool_call = {
            "id": "call_batch",
            "function": {
                "name": "execute_services",
                "arguments": {
                    "calls": [
                        {"domain": "light", "service": "turn_on", "entity_id": "light.kitchen"},
                        {"domain": "light", "service": "turn_on", "entity_id": "light.study"},
                    ]
                },
            },
        }
        result = await execute_tool_call(
            hass, tool_call, {"light.kitchen", "light.study"}
        )
        assert result["success"] is True
        assert len(result["results"]) == 2

    @pytest.mark.asyncio
    async def test_execute_services_batch_partial_failure(self):
        hass = MagicMock()
        hass.services.async_call = AsyncMock()
        hass.bus.async_fire = MagicMock()

        tool_call = {
            "id": "call_batch",
            "function": {
                "name": "execute_services",
                "arguments": {
                    "calls": [
                        {"domain": "light", "service": "turn_on", "entity_id": "light.kitchen"},
                        {"domain": "light", "service": "turn_on", "entity_id": "light.secret"},
                    ]
                },
            },
        }
        result = await execute_tool_call(
            hass, tool_call, {"light.kitchen"}
        )
        assert result["success"] is False
        assert len(result["results"]) == 2

    @pytest.mark.asyncio
    async def test_execute_services_empty_calls(self):
        hass = MagicMock()

        tool_call = {
            "id": "call_batch",
            "function": {
                "name": "execute_services",
                "arguments": {"calls": []},
            },
        }
        result = await execute_tool_call(hass, tool_call, set())
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_fires_tool_invoked_event(self):
        hass = MagicMock()
        hass.services.async_call = AsyncMock()
        hass.bus.async_fire = MagicMock()

        tool_call = {
            "id": "call_1",
            "function": {
                "name": "execute_service",
                "arguments": '{"domain": "light", "service": "turn_on", "entity_id": "light.kitchen"}',
            },
        }
        await execute_tool_call(hass, tool_call, {"light.kitchen"})

        hass.bus.async_fire.assert_called_once()
        event_name = hass.bus.async_fire.call_args[0][0]
        assert event_name == "agent_bridge_tool_invoked"
