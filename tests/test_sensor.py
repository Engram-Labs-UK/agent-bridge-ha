"""Tests for sensor platform entities."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.agent_bridge.const import DOMAIN
from custom_components.agent_bridge.sensor import (
    AgentCountSensor,
    BridgeStatusSensor,
    _device_info,
)


@pytest.fixture
def mock_coordinator():
    coord = MagicMock()
    coord.data = {
        "connected": True,
        "bridge_status": "ok",
        "bridge_version": "3.2.0",
        "bridge_uptime": 12345,
        "agent_count_healthy": 3,
        "agent_count_total": 4,
        "agents": [],
        "last_poll": "2026-04-05T00:00:00Z",
    }
    return coord


@pytest.fixture
def mock_entry():
    entry = MagicMock()
    entry.entry_id = "test_entry"
    return entry


class TestBridgeStatusSensor:

    def test_native_value(self, mock_coordinator, mock_entry):
        sensor = BridgeStatusSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == "ok"

    def test_extra_attributes(self, mock_coordinator, mock_entry):
        sensor = BridgeStatusSensor(mock_coordinator, mock_entry)
        attrs = sensor.extra_state_attributes
        assert attrs["version"] == "3.2.0"
        assert attrs["uptime_seconds"] == 12345

    def test_tool_surface_attributes(self, mock_entry):
        """US0028/AC4: /v1/health toolSurface + readOnlySafe surface as attributes."""
        coord = MagicMock()
        coord.data = {
            "bridge_status": "warning",
            "bridge_version": "4.36.0",
            "bridge_uptime": 10,
            "tool_surface": "execute_service",
            "read_only_safe": False,
        }
        sensor = BridgeStatusSensor(coord, mock_entry)
        assert sensor.native_value == "warning"  # distinct tri-state
        attrs = sensor.extra_state_attributes
        assert attrs["tool_surface"] == "execute_service"
        assert attrs["read_only_safe"] is False

    def test_no_data(self, mock_entry):
        coord = MagicMock()
        coord.data = None
        sensor = BridgeStatusSensor(coord, mock_entry)
        assert sensor.native_value is None
        assert sensor.extra_state_attributes == {}

    def test_unique_id(self, mock_coordinator, mock_entry):
        sensor = BridgeStatusSensor(mock_coordinator, mock_entry)
        assert sensor._attr_unique_id == "test_entry_bridge_status"

    def test_name(self, mock_coordinator, mock_entry):
        sensor = BridgeStatusSensor(mock_coordinator, mock_entry)
        assert sensor.name == "Bridge Status"


class TestAgentCountSensor:

    def test_native_value(self, mock_coordinator, mock_entry):
        sensor = AgentCountSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == 3

    def test_extra_attributes(self, mock_coordinator, mock_entry):
        sensor = AgentCountSensor(mock_coordinator, mock_entry)
        attrs = sensor.extra_state_attributes
        assert attrs["total"] == 4

    def test_no_data(self, mock_entry):
        coord = MagicMock()
        coord.data = None
        sensor = AgentCountSensor(coord, mock_entry)
        assert sensor.native_value is None

    def test_name(self, mock_coordinator, mock_entry):
        sensor = AgentCountSensor(mock_coordinator, mock_entry)
        assert sensor.name == "Agent Count"


class TestDeviceInfo:

    def test_device_info_structure(self, mock_entry):
        info = _device_info(mock_entry)
        assert (DOMAIN, "test_entry") in info["identifiers"]
        assert info["name"] == "Agent Bridge"
