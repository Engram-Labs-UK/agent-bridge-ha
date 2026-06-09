"""Tests for the diagnostics platform (CR-0009)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.agent_bridge.const import DOMAIN
from custom_components.agent_bridge.diagnostics import async_get_config_entry_diagnostics


@pytest.fixture
def hass_with_entry():
    hass = MagicMock()
    coordinator = MagicMock()
    coordinator.data = {
        "connected": True,
        "bridge_status": "ok",
        "bridge_version": "4.141.0",
        "tool_surface": "full",
        "read_only_safe": False,
        "doctor": {"verdict": "HEALTHY", "findings": []},
        "usage": {"cora": {"totals": {"totalIn": 1, "totalOut": 2}}},
        "agents": [{"id": "cora", "name": "Cora", "healthy": True, "crew": "deskpoint"}],
    }
    entry = MagicMock()
    entry.entry_id = "e1"
    entry.data = {"bridge_url": "http://b:18780", "bridge_token": "SECRET"}
    entry.options = {"caller_id": "cora", "context_max_chars": 13000}
    hass.data = {DOMAIN: {"e1": {"coordinator": coordinator}}}
    return hass, entry


@pytest.mark.asyncio
async def test_redacts_token_and_caller(hass_with_entry):
    hass, entry = hass_with_entry
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["entry_data"]["bridge_token"] == "**REDACTED**"
    assert diag["entry_options"]["caller_id"] == "**REDACTED**"
    # non-secret values pass through
    assert diag["entry_data"]["bridge_url"] == "http://b:18780"
    assert diag["entry_options"]["context_max_chars"] == 13000


@pytest.mark.asyncio
async def test_includes_doctor_usage_and_agents(hass_with_entry):
    hass, entry = hass_with_entry
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["doctor"]["verdict"] == "HEALTHY"
    assert diag["usage"]["cora"]["totals"]["totalIn"] == 1
    assert diag["agents"][0]["name"] == "Cora"
    assert diag["bridge_version"] == "4.141.0"
