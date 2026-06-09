"""Tests for sensor platform entities."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.agent_bridge.const import DOMAIN
from custom_components.agent_bridge.sensor import (
    AgentCostSensor,
    AgentCountSensor,
    AgentTokensSensor,
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


class TestAgentUsageSensors:
    """CR-0009: per-agent token + cost sensors."""

    @staticmethod
    def _coord(usage):
        coord = MagicMock()
        coord.data = {"usage": usage, "agents": []}
        return coord

    def test_tokens_sum_in_and_out(self, mock_entry):
        coord = self._coord({"cora": {"totals": {"totalIn": 100, "totalOut": 40, "turnCount": 5}}})
        s = AgentTokensSensor(coord, mock_entry, "cora", "Cora (deskpoint)", None)
        assert s.native_value == 140
        assert s.extra_state_attributes["turns"] == 5

    def test_tokens_none_when_no_usage(self, mock_entry):
        s = AgentTokensSensor(self._coord({}), mock_entry, "cora", "Cora", None)
        assert s.native_value is None

    def test_tokens_none_on_null_field(self, mock_entry):
        # BG0006: a null totalIn must not raise (int(None) -> TypeError); the
        # remaining numeric field still counts.
        coord = self._coord({"cora": {"totals": {"totalIn": None, "totalOut": 5}}})
        s = AgentTokensSensor(coord, mock_entry, "cora", "Cora", None)
        assert s.native_value == 5

    def test_tokens_none_on_non_numeric(self, mock_entry):
        coord = self._coord({"cora": {"totals": {"totalIn": "lots", "totalOut": "n/a"}}})
        s = AgentTokensSensor(coord, mock_entry, "cora", "Cora", None)
        assert s.native_value is None

    def test_tokens_none_on_empty_totals(self, mock_entry):
        # BG0006: present-but-empty totals -> unknown, not a misleading 0.
        coord = self._coord({"cora": {"totals": {}}})
        s = AgentTokensSensor(coord, mock_entry, "cora", "Cora", None)
        assert s.native_value is None

    def test_cost_none_on_null(self, mock_entry):
        coord = self._coord({"cora": {"estimatedTotalCostGBP": None}})
        s = AgentCostSensor(coord, mock_entry, "cora", "Cora", None)
        assert s.native_value is None

    def test_cost_ignores_bool(self, mock_entry):
        # bool is an int subclass; True must not become cost 1.0.
        coord = self._coord({"cora": {"estimatedTotalCostGBP": True}})
        s = AgentCostSensor(coord, mock_entry, "cora", "Cora", None)
        assert s.native_value is None

    def test_cost_value(self, mock_entry):
        coord = self._coord({"cora": {"estimatedTotalCostGBP": 0.42}})
        s = AgentCostSensor(coord, mock_entry, "cora", "Cora", None)
        assert s.native_value == 0.42

    def test_cost_none_when_no_pricing(self, mock_entry):
        coord = self._coord({"cora": {"totals": {"totalIn": 1, "totalOut": 1}}})
        s = AgentCostSensor(coord, mock_entry, "cora", "Cora", None)
        assert s.native_value is None

    def test_device_identifier_matches_agent_device(self, mock_entry):
        # Must share the conversation/ai_task device tuple: (DOMAIN, entry_subentry)
        s = AgentTokensSensor(self._coord({}), mock_entry, "cora", "Cora", "sub1")
        assert (DOMAIN, "test_entry_sub1") in s._attr_device_info["identifiers"]
