"""Tests for the conversation agent -- prompt building, routing, continuation detection."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock

from custom_components.agent_bridge.conversation import (
    _build_source_context,
    _build_system_prompt,
    _detect_continuation,
    _parse_confirm_marker,
    _resolve_area_name,
    _resolve_presence,
    _resolve_source_type,
    _resolve_upcoming,
    _safety_caution,
    _session_channel,
    _session_scope,
)
from custom_components.agent_bridge.exposure import build_recent_changes


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

    def test_grounding_extras_rendered(self):
        result = _build_source_context(
            {
                "source_type": "text",
                "presence": "home: Darren; away: Sam",
                "upcoming": "next alarm 06:30",
                "recent_changes": "Thermostat (climate.x): 23 (changed 20m ago)",
            }
        )
        assert "Presence: home: Darren; away: Sam" in result
        assert "Upcoming: next alarm 06:30" in result
        assert "Recently changed:\nThermostat (climate.x): 23 (changed 20m ago)" in result


class TestResolvePresence:
    def test_home_and_away(self):
        hass = MagicMock()
        people = [
            MagicMock(name="x", state="home"),
            MagicMock(state="not_home"),
        ]
        people[0].name = "Darren"
        people[1].name = "Sam"
        hass.states.async_all.side_effect = lambda d: people if d == "person" else []
        assert _resolve_presence(hass) == "home: Darren; away: Sam"

    def test_none_when_no_persons(self):
        hass = MagicMock()
        hass.states.async_all.side_effect = lambda d: []
        assert _resolve_presence(hass) is None


class TestResolveUpcoming:
    def test_next_alarm_and_calendar(self):
        hass = MagicMock()
        alarm = MagicMock(entity_id="sensor.phone_next_alarm", state="2026-06-06T06:30:00")
        cal = MagicMock(state="on")
        cal.attributes = {"message": "Bin day", "start_time": "2026-06-06 07:00"}

        def _all(domain):
            return {"sensor": [alarm], "calendar": [cal]}.get(domain, [])

        hass.states.async_all.side_effect = _all
        out = _resolve_upcoming(hass)
        assert "next alarm 2026-06-06T06:30:00" in out
        assert "calendar: Bin day at 2026-06-06 07:00" in out

    def test_none_when_nothing(self):
        hass = MagicMock()
        hass.states.async_all.side_effect = lambda d: []
        assert _resolve_upcoming(hass) is None


class TestBuildRecentChanges:
    def test_recent_within_window_sorted(self):
        now = datetime(2026, 6, 5, 14, 0, 0)
        hass = MagicMock()
        recent = MagicMock(entity_id="climate.x", state="23")
        recent.name = "Thermostat"
        recent.last_changed = now - timedelta(minutes=20)
        old = MagicMock(entity_id="light.y", state="on")
        old.name = "Lamp"
        old.last_changed = now - timedelta(hours=5)
        states = {"climate.x": recent, "light.y": old}
        hass.states.get.side_effect = lambda eid: states.get(eid)

        out = build_recent_changes(hass, ["climate.x", "light.y"], now=now, window_s=1800)
        assert "Thermostat (climate.x): 23 (changed 20m ago)" in out
        assert "light.y" not in out  # 5h ago is outside the 30-min window

    def test_empty_when_nothing_recent(self):
        now = datetime(2026, 6, 5, 14, 0, 0)
        hass = MagicMock()
        hass.states.get.side_effect = lambda eid: None
        assert build_recent_changes(hass, ["a.b"], now=now) == ""


class TestParseConfirmMarker:
    """US0036: strip [confirm:LEVEL] and surface severity."""

    def test_high_marker_stripped(self):
        text, sev = _parse_confirm_marker("[confirm:high] Shall I unlock the door?")
        assert text == "Shall I unlock the door?"
        assert sev == "high"

    def test_normal_marker(self):
        text, sev = _parse_confirm_marker("[confirm:normal] Turn off the lamp?")
        assert text == "Turn off the lamp?"
        assert sev == "normal"

    def test_no_marker(self):
        text, sev = _parse_confirm_marker("Done, the lights are on.")
        assert text == "Done, the lights are on."
        assert sev is None

    def test_unknown_level_untouched(self):
        text, sev = _parse_confirm_marker("[confirm:bogus] hi")
        assert text == "[confirm:bogus] hi"
        assert sev is None

    def test_empty(self):
        assert _parse_confirm_marker("") == ("", None)


class TestSafetyCautionConfirm:
    def test_caution_mentions_confirm_marker(self):
        out = _safety_caution({"lock"})
        assert "[confirm:high]" in out
        assert "lock" in out

    def test_no_caution_without_risky_domains(self):
        assert _safety_caution(set()) == ""


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


class TestSessionScope:
    def test_device_scope(self):
        ui = MagicMock(device_id="d1")
        assert _session_scope(ui) == "dev:d1"

    def test_user_scope_when_no_device(self):
        ui = MagicMock(device_id=None, context=MagicMock(user_id="u1"))
        assert _session_scope(ui) == "usr:u1"

    def test_default_scope(self):
        ui = MagicMock(device_id=None, context=MagicMock(user_id=None))
        assert _session_scope(ui) == "default"


class TestSessionChannel:
    """US0032: idle-windowed channel-key rotation."""

    def test_format_and_first_epoch(self):
        epochs: dict = {}
        t0 = datetime(2026, 6, 5, 14, 0, 0)
        ch = _session_channel(epochs, agent_id="cora", scope="dev:d1", idle_window=600, now=t0)
        assert ch == "ha:cora:dev:d1:1"

    def test_reuse_within_idle_window(self):
        epochs: dict = {}
        t0 = datetime(2026, 6, 5, 14, 0, 0)
        first = _session_channel(epochs, agent_id="cora", scope="dev:d1", idle_window=600, now=t0)
        second = _session_channel(
            epochs,
            agent_id="cora",
            scope="dev:d1",
            idle_window=600,
            now=t0 + timedelta(seconds=60),
        )
        assert first == second == "ha:cora:dev:d1:1"

    def test_rotate_after_idle_window(self):
        epochs: dict = {}
        t0 = datetime(2026, 6, 5, 14, 0, 0)
        _session_channel(epochs, agent_id="cora", scope="dev:d1", idle_window=600, now=t0)
        rotated = _session_channel(
            epochs,
            agent_id="cora",
            scope="dev:d1",
            idle_window=600,
            now=t0 + timedelta(seconds=601),
        )
        assert rotated == "ha:cora:dev:d1:2"

    def test_idle_window_value_respected(self):
        epochs: dict = {}
        t0 = datetime(2026, 6, 5, 14, 0, 0)
        _session_channel(epochs, agent_id="cora", scope="dev:d1", idle_window=10, now=t0)
        rotated = _session_channel(
            epochs,
            agent_id="cora",
            scope="dev:d1",
            idle_window=10,
            now=t0 + timedelta(seconds=15),
        )
        assert rotated.endswith(":2")

    def test_scopes_are_independent(self):
        epochs: dict = {}
        t0 = datetime(2026, 6, 5, 14, 0, 0)
        a = _session_channel(epochs, agent_id="cora", scope="dev:d1", idle_window=600, now=t0)
        b = _session_channel(epochs, agent_id="cora", scope="dev:d2", idle_window=600, now=t0)
        assert a == "ha:cora:dev:d1:1"
        assert b == "ha:cora:dev:d2:1"

    def test_backwards_clock_jump_rotates(self):
        # NTP/manual rewind: a negative gap must mint a fresh session, not stick.
        epochs: dict = {}
        t0 = datetime(2026, 6, 5, 14, 0, 0)
        _session_channel(epochs, agent_id="cora", scope="dev:d1", idle_window=600, now=t0)
        rotated = _session_channel(
            epochs,
            agent_id="cora",
            scope="dev:d1",
            idle_window=600,
            now=t0 - timedelta(seconds=120),
        )
        assert rotated == "ha:cora:dev:d1:2"

    def test_stale_scopes_are_pruned(self):
        # Entries past the bridge session TTL (24h) are dropped to bound the map.
        epochs: dict = {}
        t0 = datetime(2026, 6, 5, 14, 0, 0)
        _session_channel(epochs, agent_id="cora", scope="dev:old", idle_window=600, now=t0)
        _session_channel(
            epochs,
            agent_id="cora",
            scope="dev:new",
            idle_window=600,
            now=t0 + timedelta(seconds=90000),  # > 24h after dev:old
        )
        assert "dev:old" not in epochs
        assert "dev:new" in epochs


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
