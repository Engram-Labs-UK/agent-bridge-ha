"""Agent Bridge integration for Home Assistant."""

from __future__ import annotations

import logging
import secrets
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .client import BridgeClient
from .const import (
    CONF_BRIDGE_TOKEN,
    CONF_BRIDGE_URL,
    CONF_CALLER_ID,
    CONF_SSL_VERIFY,
    CONF_THINKING_TIMEOUT,
    DEFAULT_CALLER_ID,
    DEFAULT_THINKING_TIMEOUT,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import AgentBridgeCoordinator

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = f"{DOMAIN}.sessions"
STORAGE_VERSION = 1


class SessionManager:
    """Manage agent-scoped session IDs persisted to HA Store."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._sessions: dict[str, str] = {}

    async def async_load(self) -> None:
        """Load sessions from HA Store."""
        data = await self._store.async_load()
        if isinstance(data, dict):
            self._sessions = data.get("sessions", {})

    async def async_save(self) -> None:
        """Save sessions to HA Store."""
        await self._store.async_save({"sessions": self._sessions})

    def get_or_create(self, agent_id: str) -> str:
        """Get existing session ID for an agent, or create a new one."""
        if agent_id not in self._sessions:
            random_hex = secrets.token_hex(4)
            self._sessions[agent_id] = f"agent-{agent_id}-assist_{random_hex}"
        return self._sessions[agent_id]

    @property
    def sessions(self) -> dict[str, str]:
        """Return all sessions."""
        return dict(self._sessions)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Agent Bridge from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)
    ssl_verify = entry.options.get(CONF_SSL_VERIFY, True)
    timeout = entry.options.get(CONF_THINKING_TIMEOUT, DEFAULT_THINKING_TIMEOUT)
    caller_id = entry.options.get(CONF_CALLER_ID, DEFAULT_CALLER_ID)

    client = BridgeClient(
        session,
        entry.data[CONF_BRIDGE_URL],
        entry.data[CONF_BRIDGE_TOKEN],
        timeout=timeout,
        ssl_verify=ssl_verify,
        caller_id=caller_id,
    )

    coordinator = AgentBridgeCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    session_manager = SessionManager(hass)
    await session_manager.async_load()

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
        "session_manager": session_manager,
    }

    # The conversation entity platform (in PLATFORMS) creates one
    # ConversationEntity per bridge agent and auto-registers it as an Assist
    # agent -- the legacy direct-registration call is gone (US0025).
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Listen for options updates
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    # Register services
    from .services import async_setup_services

    await async_setup_services(hass)

    # Register webhook (Phase 2 -- graceful fallback to polling)
    from .webhook import async_register_webhook, async_register_with_bridge

    webhook_id = await async_register_webhook(hass, entry.entry_id)
    subscription_id = None
    if webhook_id:
        subscription_id = await async_register_with_bridge(hass, entry.entry_id, webhook_id)
    hass.data[DOMAIN][entry.entry_id]["webhook_id"] = webhook_id
    hass.data[DOMAIN][entry.entry_id]["webhook_subscription_id"] = subscription_id

    # Drift defences (US0029): check agent-context now, and re-check whenever the
    # bridge announces an upgrade (the webhook fires EVENT_BRIDGE_UPGRADED, US0024).
    from .const import EVENT_BRIDGE_UPGRADED
    from .drift import async_check_agent_context_drift

    await async_check_agent_context_drift(hass, entry)

    async def _on_bridge_upgraded(_event: Any) -> None:
        await async_check_agent_context_drift(hass, entry)

    entry.async_on_unload(hass.bus.async_listen(EVENT_BRIDGE_UPGRADED, _on_bridge_upgraded))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Agent Bridge config entry."""
    # Save sessions before unload
    data = hass.data[DOMAIN].get(entry.entry_id, {})
    session_manager = data.get("session_manager")
    if isinstance(session_manager, SessionManager):
        await session_manager.async_save()

    # Unregister webhook
    from .webhook import async_unregister_webhook

    await async_unregister_webhook(
        hass,
        entry.entry_id,
        data.get("webhook_id"),
        data.get("webhook_subscription_id"),
    )

    # The conversation entities unload with the platform
    # (async_unload_platforms below) -- the legacy direct-unregister call is gone (US0025).

    # Unregister services (only if last entry)
    if len(hass.data.get(DOMAIN, {})) <= 1:
        from .services import async_unload_services

        await async_unload_services(hass)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update -- reload the integration to apply changes."""
    await hass.config_entries.async_reload(entry.entry_id)
