"""Tests for the v4.36 discovery/health surface (US0028) and drift defences (US0029)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.agent_bridge.client import BridgeClient
from custom_components.agent_bridge.const import DOMAIN, TESTED_BRIDGE_VERSION
from custom_components.agent_bridge.conversation import _is_voice_capable
from custom_components.agent_bridge.coordinator import (
    AgentBridgeCoordinator,
    _map_tristate,
)
from custom_components.agent_bridge.drift import (
    async_check_agent_context_drift,
    async_check_doctor_verdict,
)


def _mock_response(json_data):
    resp = AsyncMock()
    resp.status = 200
    resp.content_type = "application/json"
    resp.json = AsyncMock(return_value=json_data)
    resp.text = AsyncMock(return_value="")
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


# --- US0028/AC1: x-bridge-mcp-caller header ---


class TestCallerHeader:
    @pytest.mark.asyncio
    async def test_caller_header_present_on_discover(self):
        session = MagicMock(spec=aiohttp.ClientSession)
        client = BridgeClient(session, "http://b:18780", "tok", caller_id="homeassistant")
        session.request = MagicMock(return_value=_mock_response({"agents": []}))
        await client.discover()
        headers = session.request.call_args.kwargs["headers"]
        assert headers["x-bridge-mcp-caller"] == "homeassistant"

    def test_no_caller_header_when_unset(self):
        session = MagicMock(spec=aiohttp.ClientSession)
        client = BridgeClient(session, "http://b:18780", "tok")
        assert "x-bridge-mcp-caller" not in client._headers


# --- US0028/AC2: health block + circuit makes a busy/open agent distinct ---


class TestParseAgentHealthBlock:
    def _coord(self):
        return AgentBridgeCoordinator(MagicMock(), MagicMock())

    def test_ready_closed_is_healthy(self):
        info = self._coord()._parse_agent(
            {"id": "cora", "health": {"state": "ready", "circuit": "closed"}}
        )
        assert info["healthy"] is True
        assert info["circuit"] == "closed"

    def test_open_circuit_is_not_healthy(self):
        info = self._coord()._parse_agent(
            {"id": "cora", "health": {"state": "ready", "circuit": "open"}}
        )
        assert info["healthy"] is False  # distinct from healthy

    def test_captures_metrics_and_taxonomy(self):
        info = self._coord()._parse_agent(
            {
                "id": "cora",
                "health": {"state": "ready", "circuit": "closed", "inflight": 4},
                "metrics": {"latency": 120, "requests": 99, "errors": 3},
                "agentClass": "Chatbot",
                "capabilityEnvelope": "chatbot",
                "isOrchestrator": False,
                "deprecated": True,
            }
        )
        assert info["inflight"] == 4
        assert info["latency_ms"] == 120
        assert info["errors"] == 3
        assert info["capability_envelope"] == "chatbot"
        assert info["deprecated"] is True

    def test_legacy_status_still_parses(self):
        info = self._coord()._parse_agent({"id": "cora", "status": "healthy"})
        assert info["healthy"] is True


# --- US0028/AC3: capabilityEnvelope gating ---


class TestVoiceCapableGating:
    def test_workerbot_excluded(self):
        assert _is_voice_capable({"agent_class": "workerbot"}) is False

    def test_chatbot_excluded(self):
        # CR-0003: chatbots (no tools) can't actuate -- not selectable.
        assert _is_voice_capable({"agent_class": "chatbot"}) is False

    def test_orchestrator_excluded(self):
        assert _is_voice_capable({"is_orchestrator": True}) is False

    def test_bare_model_excluded(self):
        assert _is_voice_capable({"identity_substrate": "none"}) is False

    def test_full_agent_allowed(self):
        assert _is_voice_capable({"agent_class": "agent", "identity_substrate": "persona"}) is True

    def test_unknown_allowed_for_backcompat(self):
        assert _is_voice_capable(None) is True
        assert _is_voice_capable({}) is True


# --- US0028/AC4: /v1/health tri-state mapping ---


class TestTristate:
    def test_warning_maps_distinctly(self):
        assert _map_tristate("warning", "ok") == "warning"
        assert _map_tristate("degraded", "ok") == "warning"

    def test_ready_maps_ok_error_maps_error(self):
        assert _map_tristate("ready", "unknown") == "ok"
        assert _map_tristate("error", "ok") == "error"

    def test_unknown_falls_back(self):
        assert _map_tristate(None, "ok") == "ok"
        assert _map_tristate("weird", "degraded") == "degraded"

    @pytest.mark.asyncio
    async def test_poll_v1_health_non_fatal(self):
        coord = AgentBridgeCoordinator(MagicMock(), MagicMock())
        # client.agent_health raising must not propagate.
        coord.client.agent_health = AsyncMock(side_effect=RuntimeError("boom"))
        assert await coord._poll_v1_health() is None


# --- US0029/AC1: agent-context drift -> HA repair issue ---


class TestDriftRepairIssue:
    @pytest.mark.asyncio
    async def test_deprecation_raises_issue(self, hass):
        from homeassistant.helpers import issue_registry as ir

        client = MagicMock()
        client.agent_context = AsyncMock(
            return_value={
                "version": TESTED_BRIDGE_VERSION,
                "deprecations": [{"field": "old_thing"}],
            }
        )
        entry = MagicMock()
        entry.entry_id = "entry_1"
        hass.data.setdefault(DOMAIN, {})["entry_1"] = {"client": client}

        drifted = await async_check_agent_context_drift(hass, entry)
        assert drifted is True
        reg = ir.async_get(hass)
        assert reg.async_get_issue(DOMAIN, "bridge_drift_entry_1") is not None

    @pytest.mark.asyncio
    async def test_newer_bridge_raises_issue(self, hass):
        from homeassistant.helpers import issue_registry as ir

        client = MagicMock()
        client.agent_context = AsyncMock(return_value={"version": "99.0.0", "deprecations": []})
        entry = MagicMock()
        entry.entry_id = "entry_2"
        hass.data.setdefault(DOMAIN, {})["entry_2"] = {"client": client}

        assert await async_check_agent_context_drift(hass, entry) is True
        reg = ir.async_get(hass)
        assert reg.async_get_issue(DOMAIN, "bridge_drift_entry_2") is not None

    @pytest.mark.asyncio
    async def test_no_drift_no_issue(self, hass):
        from homeassistant.helpers import issue_registry as ir

        client = MagicMock()
        client.agent_context = AsyncMock(
            return_value={"version": TESTED_BRIDGE_VERSION, "deprecations": []}
        )
        entry = MagicMock()
        entry.entry_id = "entry_3"
        hass.data.setdefault(DOMAIN, {})["entry_3"] = {"client": client}

        assert await async_check_agent_context_drift(hass, entry) is False
        reg = ir.async_get(hass)
        assert reg.async_get_issue(DOMAIN, "bridge_drift_entry_3") is None


class TestDoctorRepairIssue:
    """CR-0009/CR-0012: the fleet-doctor verdict raises/clears an HA repair issue
    only when the opt-in 'doctor_alerts' option is enabled."""

    @staticmethod
    def _entry_with_doctor(hass, entry_id, doctor, *, alerts=True):
        coordinator = MagicMock()
        coordinator.data = {"doctor": doctor}
        entry = MagicMock()
        entry.entry_id = entry_id
        entry.options = {"doctor_alerts": alerts}
        hass.data.setdefault(DOMAIN, {})[entry_id] = {"coordinator": coordinator}
        return entry

    @pytest.mark.asyncio
    async def test_opt_in_off_raises_nothing(self, hass):
        # CR-0012: with the alerts option off, a CRITICAL verdict raises no repair.
        from homeassistant.helpers import issue_registry as ir

        entry = self._entry_with_doctor(
            hass, "doc_off", {"verdict": "CRITICAL", "findings": []}, alerts=False
        )
        async_check_doctor_verdict(hass, entry)
        assert ir.async_get(hass).async_get_issue(DOMAIN, "fleet_doctor_doc_off") is None

    @pytest.mark.asyncio
    async def test_critical_raises_error_issue(self, hass):
        from homeassistant.helpers import issue_registry as ir

        entry = self._entry_with_doctor(
            hass,
            "doc_1",
            {
                "verdict": "CRITICAL",
                "findings": [{"severity": "critical", "area": "providers", "detail": "no key"}],
            },
        )
        async_check_doctor_verdict(hass, entry)
        issue = ir.async_get(hass).async_get_issue(DOMAIN, "fleet_doctor_doc_1")
        assert issue is not None
        assert issue.severity == ir.IssueSeverity.ERROR

    @pytest.mark.asyncio
    async def test_warning_does_not_raise_issue(self, hass):
        # BG0011: an advisory WARNING (e.g. an idle/quiet fleet) must not nag via a
        # repair notification; it stays in diagnostics only.
        from homeassistant.helpers import issue_registry as ir

        entry = self._entry_with_doctor(
            hass,
            "doc_2",
            {"verdict": "WARNING", "findings": [{"area": "fleet", "detail": "fleet quiet"}]},
        )
        async_check_doctor_verdict(hass, entry)
        assert ir.async_get(hass).async_get_issue(DOMAIN, "fleet_doctor_doc_2") is None

    @pytest.mark.asyncio
    async def test_healthy_clears_issue(self, hass):
        from homeassistant.helpers import issue_registry as ir

        # raise, then clear with a HEALTHY verdict on the same entry
        entry = self._entry_with_doctor(hass, "doc_3", {"verdict": "CRITICAL", "findings": []})
        async_check_doctor_verdict(hass, entry)
        assert ir.async_get(hass).async_get_issue(DOMAIN, "fleet_doctor_doc_3") is not None

        hass.data[DOMAIN]["doc_3"]["coordinator"].data = {"doctor": {"verdict": "HEALTHY"}}
        async_check_doctor_verdict(hass, entry)
        assert ir.async_get(hass).async_get_issue(DOMAIN, "fleet_doctor_doc_3") is None

    @pytest.mark.asyncio
    async def test_gate_records_applied_verdict(self, hass):
        # BG0007: the check records the applied verdict and a repeated identical
        # call is a no-op (the issue persists).
        from homeassistant.helpers import issue_registry as ir

        entry = self._entry_with_doctor(hass, "doc_4", {"verdict": "CRITICAL", "findings": []})
        async_check_doctor_verdict(hass, entry)
        coord = hass.data[DOMAIN]["doc_4"]["coordinator"]
        assert coord._fleet_doctor_applied == "CRITICAL"

        async_check_doctor_verdict(hass, entry)  # unchanged -> no-op
        assert ir.async_get(hass).async_get_issue(DOMAIN, "fleet_doctor_doc_4") is not None
