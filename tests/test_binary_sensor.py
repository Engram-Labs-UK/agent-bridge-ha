"""Tests for binary sensor platform entities."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.agent_bridge.binary_sensor import (
    BridgeConnectedSensor,
)


@pytest.fixture
def mock_coordinator():
    coord = MagicMock()
    coord.data = {
        "connected": True,
        "agents": [
            {"id": "cora", "healthy": True, "adapter": "http-openai"},
            {"id": "claude", "healthy": False, "adapter": "cli"},
        ],
    }
    return coord


@pytest.fixture
def mock_entry():
    entry = MagicMock()
    entry.entry_id = "test_entry"
    return entry


class TestBridgeConnectedSensor:

    def test_is_on_when_connected(self, mock_coordinator, mock_entry):
        sensor = BridgeConnectedSensor(mock_coordinator, mock_entry)
        assert sensor.is_on is True

    def test_is_off_when_disconnected(self, mock_entry):
        coord = MagicMock()
        coord.data = {"connected": False, "agents": []}
        sensor = BridgeConnectedSensor(coord, mock_entry)
        assert sensor.is_on is False

    def test_none_when_no_data(self, mock_entry):
        coord = MagicMock()
        coord.data = None
        sensor = BridgeConnectedSensor(coord, mock_entry)
        assert sensor.is_on is None

    def test_unique_id(self, mock_coordinator, mock_entry):
        sensor = BridgeConnectedSensor(mock_coordinator, mock_entry)
        assert sensor._attr_unique_id == "test_entry_connected"
