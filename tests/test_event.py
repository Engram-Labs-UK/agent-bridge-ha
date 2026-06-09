"""Tests for event platform entities."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.agent_bridge.event import MessageReceivedEvent
from custom_components.agent_bridge.const import DOMAIN


@pytest.fixture
def mock_entry():
    entry = MagicMock()
    entry.entry_id = "test_entry"
    return entry


class TestMessageReceivedEvent:

    def test_event_types(self, mock_entry):
        event = MessageReceivedEvent(mock_entry)
        assert "message_received" in event._attr_event_types

    def test_unique_id(self, mock_entry):
        event = MessageReceivedEvent(mock_entry)
        assert event._attr_unique_id == "test_entry_message_received"

    def test_name(self, mock_entry):
        event = MessageReceivedEvent(mock_entry)
        assert event.name == "Message Received"

    def test_device_info(self, mock_entry):
        event = MessageReceivedEvent(mock_entry)
        assert (DOMAIN, "test_entry") in event._attr_device_info["identifiers"]
