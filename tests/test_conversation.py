"""Tests for the conversation agent -- prompt building, routing, continuation detection."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.agent_bridge.conversation import (
    _build_source_context,
    _build_system_prompt,
    _detect_continuation,
    _resolve_area_name,
    _resolve_source_type,
)


class TestBuildSystemPrompt:
    def test_all_three_layers(self):
        result = _build_system_prompt(
            source_context="[home-assistant-source]\nSource: voice (Kitchen)",
            entity_context="light.kitchen: on",
            extra_system_prompt="Be concise.",
        )
        assert "[home-assistant-source]" in result
        assert "light.kitchen: on" in result
        assert "Be concise." in result

    def test_source_before_entities(self):
        result = _build_system_prompt(
            source_context="[home-assistant-source]\nSource: voice (Kitchen)",
            entity_context="entities here",
            extra_system_prompt=None,
        )
        idx_source = result.index("home-assistant-source")
        idx_entities = result.index("entities here")
        assert idx_source < idx_entities

    def test_no_source(self):
        result = _build_system_prompt(
            source_context="",
            entity_context="entities",
            extra_system_prompt=None,
        )
        assert "home-assistant-source" not in result
        assert "entities" in result

    def test_no_entity_context(self):
        result = _build_system_prompt(
            source_context="[home-assistant-source]\nSource: voice",
            entity_context="",
            extra_system_prompt=None,
        )
        assert "[home-assistant-source]" in result

    def test_all_empty(self):
        result = _build_system_prompt(
            source_context="",
            entity_context="",
            extra_system_prompt=None,
        )
        assert result == ""


class TestBuildSourceContext:
    def test_voice_block(self):
        result = _build_source_context(
            {
                "source_type": "voice",
                "device_name": "Kitchen Display",
                "area": "Kitchen",
                "floor": "Ground Floor",
                "language": "en",
                "local_time": "2026-06-05 14:32",
                "timezone": "Europe/London",
                "account": {"name": "Darren", "verified": False},
            }
        )
        assert result.startswith("[home-assistant-source]")
        assert 'Source: voice via "Kitchen Display" (Kitchen, Ground Floor)' in result
        assert "audio-only" in result
        assert "Darren (unverified" in result
        assert "Local time: 2026-06-05 14:32 Europe/London" in result
        assert "Language: en" in result

    def test_text_block_has_no_audio_only(self):
        result = _build_source_context({"source_type": "text", "area": "Study", "language": "en"})
        assert "Source: text (Study)" in result
        assert "Modality: text" in result
        assert "audio-only" not in result

    def test_automation_is_non_principal(self):
        result = _build_source_context({"source_type": "automation"})
        assert "automation (no human present)" in result
        assert "do not treat as a principal request" in result

    def test_area_only_when_no_floor(self):
        result = _build_source_context({"source_type": "voice", "area": "Hall"})
        assert "(Hall)" in result
        assert ", " not in result.split("Source: voice", 1)[1].split("\n", 1)[0]


class TestResolveSourceType:
    def test_voice_when_device_present(self):
        ui = MagicMock(device_id="d1")
        assert _resolve_source_type(ui) == "voice"

    def test_automation_when_parent_context_no_device(self):
        ui = MagicMock(device_id=None, context=MagicMock(parent_id="p1"))
        assert _resolve_source_type(ui) == "automation"

    def test_text_otherwise(self):
        ui = MagicMock(device_id=None, context=MagicMock(parent_id=None))
        assert _resolve_source_type(ui) == "text"


class TestDetectContinuation:
    def test_question_with_continuation_phrase(self):
        assert _detect_continuation("Would you like me to turn on all the lights?") is True

    def test_shall_i_phrase(self):
        assert _detect_continuation("Shall I set it to 21 degrees?") is True

    def test_do_you_want_phrase(self):
        assert _detect_continuation("Do you want me to close the blinds?") is True

    def test_statement_no_question(self):
        assert _detect_continuation("I've turned on the lights.") is False

    def test_exclusion_right(self):
        assert _detect_continuation("That looks good, right?") is False

    def test_exclusion_isnt_it(self):
        assert _detect_continuation("Nice weather, isn't it?") is False

    def test_exclusion_okay(self):
        assert _detect_continuation("I'll do that, okay?") is False

    def test_exclusion_let_me_know(self):
        assert _detect_continuation("Let me know if you need anything") is False

    def test_empty_string(self):
        assert _detect_continuation("") is False

    def test_question_without_phrase(self):
        # Ends with ? but no continuation phrase -- should NOT trigger
        assert _detect_continuation("How are you today?") is False

    def test_case_insensitive(self):
        assert _detect_continuation("WOULD YOU LIKE some tea?") is True


class TestResolveAreaName:
    def test_resolves_area(self):
        hass = MagicMock()
        device_reg = MagicMock()
        device_entry = MagicMock()
        device_entry.area_id = "area_kitchen"
        device_reg.async_get.return_value = device_entry

        area_reg = MagicMock()
        area = MagicMock()
        area.name = "Kitchen"
        area_reg.async_get_area.return_value = area

        with (
            __import__("unittest.mock", fromlist=["patch"]).patch(
                "custom_components.agent_bridge.conversation.dr.async_get",
                return_value=device_reg,
            ),
            __import__("unittest.mock", fromlist=["patch"]).patch(
                "custom_components.agent_bridge.conversation.ar.async_get",
                return_value=area_reg,
            ),
        ):
            result = _resolve_area_name(hass, "device_123")
        assert result == "Kitchen"

    def test_no_device_id(self):
        hass = MagicMock()
        assert _resolve_area_name(hass, None) is None

    def test_device_not_found(self):
        hass = MagicMock()
        with __import__("unittest.mock", fromlist=["patch"]).patch(
            "custom_components.agent_bridge.conversation.dr.async_get",
        ) as mock_dr:
            mock_dr.return_value.async_get.return_value = None
            result = _resolve_area_name(hass, "device_unknown")
        assert result is None

    def test_device_no_area(self):
        hass = MagicMock()
        device_entry = MagicMock()
        device_entry.area_id = None

        with __import__("unittest.mock", fromlist=["patch"]).patch(
            "custom_components.agent_bridge.conversation.dr.async_get",
        ) as mock_dr:
            mock_dr.return_value.async_get.return_value = device_entry
            result = _resolve_area_name(hass, "device_no_area")
        assert result is None
