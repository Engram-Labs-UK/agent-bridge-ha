"""Tests for entity exposure -- formatting HA state for AI context."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from custom_components.agent_bridge.exposure import (
    _format_entity,
    _get_entity_area,
    _get_relevant_attributes,
    build_entity_context,
)


def _make_state(entity_id, state="on", name=None, attributes=None):
    """Create a mock HA State object."""
    s = MagicMock()
    s.entity_id = entity_id
    s.state = state
    s.name = name or entity_id.split(".")[-1].replace("_", " ").title()
    s.attributes = attributes or {}
    return s


class TestFormatEntity:

    def test_basic_format(self):
        state = _make_state("light.kitchen", "on", "Kitchen Light")
        result = _format_entity(state, None, {})
        assert result == "Kitchen Light (light.kitchen): on"

    def test_with_area(self):
        state = _make_state("light.kitchen", "on", "Kitchen Light")
        result = _format_entity(state, "Kitchen", {})
        assert "[area: Kitchen]" in result

    def test_with_attributes(self):
        state = _make_state("light.kitchen", "on", "Kitchen Light")
        result = _format_entity(state, None, {"brightness": 75})
        assert "[brightness: 75]" in result

    def test_full_format(self):
        state = _make_state("light.kitchen", "on", "Kitchen Light")
        result = _format_entity(state, "Kitchen", {"brightness": 75, "color_temp": 300})
        assert "Kitchen Light (light.kitchen): on" in result
        assert "[area: Kitchen]" in result
        assert "[brightness: 75]" in result


class TestGetEntityArea:

    def test_entity_area_takes_priority(self):
        entity_entry = MagicMock()
        entity_entry.area_id = "area_kitchen"
        device_entry = MagicMock()
        device_entry.area_id = "area_study"
        area_reg = MagicMock()
        area = MagicMock()
        area.name = "Kitchen"
        area_reg.async_get_area.return_value = area

        result = _get_entity_area(entity_entry, device_entry, area_reg)
        assert result == "Kitchen"
        area_reg.async_get_area.assert_called_with("area_kitchen")

    def test_falls_back_to_device_area(self):
        entity_entry = MagicMock()
        entity_entry.area_id = None
        device_entry = MagicMock()
        device_entry.area_id = "area_study"
        area_reg = MagicMock()
        area = MagicMock()
        area.name = "Study"
        area_reg.async_get_area.return_value = area

        result = _get_entity_area(entity_entry, device_entry, area_reg)
        assert result == "Study"

    def test_no_area(self):
        entity_entry = MagicMock()
        entity_entry.area_id = None
        device_entry = MagicMock()
        device_entry.area_id = None
        area_reg = MagicMock()

        result = _get_entity_area(entity_entry, device_entry, area_reg)
        assert result is None

    def test_no_entity_or_device(self):
        area_reg = MagicMock()
        result = _get_entity_area(None, None, area_reg)
        assert result is None


class TestGetRelevantAttributes:

    def test_extracts_known_attributes(self):
        state = _make_state(
            "light.kitchen", "on",
            attributes={"brightness": 75, "color_temp": 300, "unknown_attr": "x"},
        )
        result = _get_relevant_attributes(state)
        assert result == {"brightness": 75, "color_temp": 300}

    def test_skips_none_values(self):
        state = _make_state(
            "light.kitchen", "on", attributes={"brightness": None}
        )
        result = _get_relevant_attributes(state)
        assert result == {}

    def test_empty_attributes(self):
        state = _make_state("sensor.temp", "22")
        result = _get_relevant_attributes(state)
        assert result == {}


class TestBuildEntityContext:

    def test_basic_context(self):
        hass = MagicMock()
        state = _make_state("light.kitchen", "on", "Kitchen Light")
        hass.states.get.return_value = state

        with patch(
            "custom_components.agent_bridge.exposure.er.async_get"
        ) as mock_er, patch(
            "custom_components.agent_bridge.exposure.dr.async_get"
        ), patch(
            "custom_components.agent_bridge.exposure.ar.async_get"
        ):
            entity_entry = MagicMock()
            entity_entry.area_id = None
            entity_entry.device_id = None
            mock_er.return_value.async_get.return_value = entity_entry

            result = build_entity_context(hass, ["light.kitchen"])
        assert "Kitchen Light (light.kitchen): on" in result

    def test_250_entity_cap(self):
        hass = MagicMock()
        entity_ids = [f"sensor.temp_{i}" for i in range(300)]

        def mock_get(eid):
            return _make_state(eid, "22", f"Temp {eid[-3:]}")

        hass.states.get.side_effect = mock_get

        with patch(
            "custom_components.agent_bridge.exposure.er.async_get"
        ) as mock_er, patch(
            "custom_components.agent_bridge.exposure.dr.async_get"
        ), patch(
            "custom_components.agent_bridge.exposure.ar.async_get"
        ):
            entry = MagicMock()
            entry.area_id = None
            entry.device_id = None
            mock_er.return_value.async_get.return_value = entry

            result = build_entity_context(hass, entity_ids)

        lines = result.strip().split("\n")
        assert len(lines) == 250

    def test_skips_unavailable_entities(self):
        hass = MagicMock()

        def mock_get(eid):
            if eid == "sensor.broken":
                return _make_state(eid, "unavailable")
            return _make_state(eid, "on", "Good")

        hass.states.get.side_effect = mock_get

        with patch(
            "custom_components.agent_bridge.exposure.er.async_get"
        ) as mock_er, patch(
            "custom_components.agent_bridge.exposure.dr.async_get"
        ), patch(
            "custom_components.agent_bridge.exposure.ar.async_get"
        ):
            entry = MagicMock()
            entry.area_id = None
            entry.device_id = None
            mock_er.return_value.async_get.return_value = entry

            result = build_entity_context(
                hass, ["sensor.broken", "light.good"]
            )
        assert "sensor.broken" not in result
        assert "light.good" in result

    def test_truncate_strategy(self):
        hass = MagicMock()

        def mock_get(eid):
            return _make_state(eid, "on", "A" * 50)

        hass.states.get.side_effect = mock_get

        with patch(
            "custom_components.agent_bridge.exposure.er.async_get"
        ) as mock_er, patch(
            "custom_components.agent_bridge.exposure.dr.async_get"
        ), patch(
            "custom_components.agent_bridge.exposure.ar.async_get"
        ):
            entry = MagicMock()
            entry.area_id = None
            entry.device_id = None
            mock_er.return_value.async_get.return_value = entry

            ids = [f"light.light_{i}" for i in range(50)]
            result = build_entity_context(
                hass, ids, max_chars=200, strategy="truncate"
            )
        assert len(result) <= 200

    def test_clear_strategy(self):
        hass = MagicMock()

        def mock_get(eid):
            return _make_state(eid, "on", "A" * 50)

        hass.states.get.side_effect = mock_get

        with patch(
            "custom_components.agent_bridge.exposure.er.async_get"
        ) as mock_er, patch(
            "custom_components.agent_bridge.exposure.dr.async_get"
        ), patch(
            "custom_components.agent_bridge.exposure.ar.async_get"
        ):
            entry = MagicMock()
            entry.area_id = None
            entry.device_id = None
            mock_er.return_value.async_get.return_value = entry

            ids = [f"light.light_{i}" for i in range(50)]
            result = build_entity_context(
                hass, ids, max_chars=200, strategy="clear"
            )
        assert result == ""

    def test_missing_state_skipped(self):
        hass = MagicMock()
        hass.states.get.return_value = None

        with patch(
            "custom_components.agent_bridge.exposure.er.async_get"
        ), patch(
            "custom_components.agent_bridge.exposure.dr.async_get"
        ), patch(
            "custom_components.agent_bridge.exposure.ar.async_get"
        ):
            result = build_entity_context(hass, ["light.gone"])
        assert result == ""
