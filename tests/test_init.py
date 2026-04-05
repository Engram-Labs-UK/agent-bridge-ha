"""Tests for integration setup and unload."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.agent_bridge import (
    SessionManager,
    STORAGE_KEY,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.agent_bridge.const import DOMAIN


class TestSessionManager:

    @pytest.mark.asyncio
    async def test_load_empty(self):
        hass = MagicMock()
        sm = SessionManager(hass)
        sm._store = MagicMock()
        sm._store.async_load = AsyncMock(return_value=None)
        await sm.async_load()
        assert sm.sessions == {}

    @pytest.mark.asyncio
    async def test_load_existing(self):
        hass = MagicMock()
        sm = SessionManager(hass)
        sm._store = MagicMock()
        sm._store.async_load = AsyncMock(
            return_value={"sessions": {"cora": "agent:cora:assist_abc123"}}
        )
        await sm.async_load()
        assert sm.sessions["cora"] == "agent:cora:assist_abc123"

    @pytest.mark.asyncio
    async def test_save(self):
        hass = MagicMock()
        sm = SessionManager(hass)
        sm._store = MagicMock()
        sm._store.async_save = AsyncMock()
        sm._sessions = {"cora": "agent:cora:assist_abc123"}
        await sm.async_save()
        sm._store.async_save.assert_called_once_with(
            {"sessions": {"cora": "agent:cora:assist_abc123"}}
        )

    def test_get_or_create_new(self):
        hass = MagicMock()
        sm = SessionManager(hass)
        session_id = sm.get_or_create("cora")
        assert session_id.startswith("agent:cora:assist_")
        assert len(session_id) > len("agent:cora:assist_")

    def test_get_or_create_existing(self):
        hass = MagicMock()
        sm = SessionManager(hass)
        sm._sessions = {"cora": "agent:cora:assist_existing"}
        assert sm.get_or_create("cora") == "agent:cora:assist_existing"

    def test_get_or_create_idempotent(self):
        hass = MagicMock()
        sm = SessionManager(hass)
        first = sm.get_or_create("cora")
        second = sm.get_or_create("cora")
        assert first == second

    def test_sessions_returns_copy(self):
        hass = MagicMock()
        sm = SessionManager(hass)
        sm._sessions = {"cora": "session_1"}
        sessions = sm.sessions
        sessions["extra"] = "should not affect internal"
        assert "extra" not in sm._sessions
