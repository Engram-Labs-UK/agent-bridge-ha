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
    CONF_ENABLE_PER_AGENT,
    CONF_SSL_VERIFY,
    CONF_THINKING_TIMEOUT,
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

    client = BridgeClient(
        session,
        entry.data[CONF_BRIDGE_URL],
        entry.data[CONF_BRIDGE_TOKEN],
        timeout=timeout,
        ssl_verify=ssl_verify,
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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register conversation agent
    from .conversation import async_setup_conversation_agent

    await async_setup_conversation_agent(hass, entry)

    # Register per-agent conversation agents if enabled
    if entry.options.get(CONF_ENABLE_PER_AGENT, False):
        from .conversation import async_setup_per_agent_conversations

        agents = coordinator.data.get("agents", []) if coordinator.data else []
        await async_setup_per_agent_conversations(hass, entry, agents)

    # Listen for options updates (e.g. toggling per-agent entities)
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

    # Unregister conversation agent
    from .conversation import async_unload_conversation_agent

    await async_unload_conversation_agent(hass, entry)

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
