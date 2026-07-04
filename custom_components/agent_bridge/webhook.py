"""Webhook handler for real-time bridge events."""

from __future__ import annotations

import logging

from aiohttp.web import Request, Response
from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant

from .const import (
    BRIDGE_WEBHOOK_EVENTS,
    CONF_WEBHOOK_SUBSCRIPTION_ID,
    DOMAIN,
    EVENT_BRIDGE_UPGRADED,
)

_LOGGER = logging.getLogger(__name__)

# Bridge events that should trigger a coordinator refresh (roster changed).
_REFRESH_EVENTS = frozenset({"agent:registered", "agent:unregistered", "agent:updated"})


async def async_register_webhook(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> str | None:
    """Register the persistent webhook with HA and return the webhook ID.

    CR-0014: the id is generated once and persisted in ``entry.data`` so
    restarts reuse it (no bridge-subscription churn); registration is
    local-only and POST-only (the bridge posts from the LAN). HA webhooks are
    unauthenticated by design -- the id is the credential, so it is logged at
    DEBUG only.
    """
    webhook_id = entry.data.get(CONF_WEBHOOK_ID)
    if not webhook_id:
        webhook_id = webhook.async_generate_id()
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_WEBHOOK_ID: webhook_id}
        )

    webhook.async_register(
        hass,
        DOMAIN,
        "Agent Bridge",
        webhook_id,
        _handle_webhook,
        local_only=True,
        allowed_methods=["POST"],
    )

    _LOGGER.debug("Registered HA webhook: %s", webhook_id)
    return webhook_id


async def async_cleanup_stale_subscription(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Best-effort unregister of a bridge subscription left by a previous run.

    CR-0014: with a persistent webhook id, a subscription leaked by an unclean
    shutdown would keep delivering (duplicate events); drop it before
    registering the fresh one so at most one live subscription exists.
    """
    stale = entry.data.get(CONF_WEBHOOK_SUBSCRIPTION_ID)
    if not stale:
        return
    client = hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).get("client")
    if client is None:
        return
    try:
        await client.unregister_webhook(stale)
        _LOGGER.debug("Unregistered stale bridge webhook subscription: %s", stale)
    except Exception:
        _LOGGER.debug("Stale bridge webhook subscription cleanup failed (ignored): %s", stale)


async def async_register_with_bridge(
    hass: HomeAssistant,
    entry_id: str,
    webhook_id: str,
) -> str | None:
    """Register the webhook URL with the bridge.

    Returns the bridge subscription ID, or None if registration fails.
    Failure is non-fatal: the integration falls back to polling.
    """
    from homeassistant.helpers.network import get_url

    data = hass.data.get(DOMAIN, {}).get(entry_id, {})
    client = data.get("client")
    if not client:
        return None

    try:
        ha_url = get_url(hass, allow_internal=True, allow_external=False)
    except Exception:
        _LOGGER.info("No HA URL available for webhook registration, using polling only")
        return None

    callback_url = f"{ha_url}/api/webhook/{webhook_id}"

    try:
        result = await client.register_webhook(callback_url, list(BRIDGE_WEBHOOK_EVENTS))
        sub_id = result.get("id") if isinstance(result, dict) else None
        _LOGGER.info("Registered bridge webhook subscription: %s", sub_id)
        return sub_id
    except Exception:
        _LOGGER.warning("Bridge webhook registration failed, continuing with polling only")
        return None


async def async_unregister_webhook(
    hass: HomeAssistant,
    entry_id: str,
    webhook_id: str | None,
    subscription_id: str | None,
) -> None:
    """Unregister the webhook from both HA and the bridge."""
    # Unregister from bridge
    if subscription_id:
        data = hass.data.get(DOMAIN, {}).get(entry_id, {})
        client = data.get("client")
        if client:
            try:
                await client.unregister_webhook(subscription_id)
                _LOGGER.info("Unregistered bridge webhook: %s", subscription_id)
            except Exception:
                _LOGGER.warning("Failed to unregister bridge webhook: %s", subscription_id)

    # Unregister from HA
    if webhook_id:
        webhook.async_unregister(hass, webhook_id)
        _LOGGER.debug("Unregistered HA webhook: %s", webhook_id)


async def _handle_webhook(
    hass: HomeAssistant,
    webhook_id: str,
    request: Request,
) -> Response | None:
    """Handle incoming webhook events from the bridge."""
    try:
        payload = await request.json()
    except Exception:
        _LOGGER.warning("Invalid webhook payload received")
        return Response(status=400)
    # BG0014: valid JSON that is not an object gets the same clean 400.
    if not isinstance(payload, dict):
        _LOGGER.warning("Invalid webhook payload received (not a JSON object)")
        return Response(status=400)

    event_type = payload.get("event")
    event_data = payload.get("data", {})

    _LOGGER.debug("Webhook event: %s", event_type)

    if event_type == "bridge:upgraded":
        # The drift signal the CR-0002 audit exists for -- fire an HA event so the
        # drift-detection consumer (US0029) can react without polling (US0024/AC3).
        hass.bus.async_fire(EVENT_BRIDGE_UPGRADED, event_data)
    elif event_type == "agent:health-changed":
        for coordinator in _iter_coordinators(hass):
            await coordinator.async_push_webhook_data(event_data)
    elif event_type in _REFRESH_EVENTS:
        # Roster changed -- pull a fresh discovery rather than wait for the poll.
        for coordinator in _iter_coordinators(hass):
            await coordinator.async_request_refresh()
    elif event_type == "message:error":
        _LOGGER.warning("Bridge reported a message error: %s", event_data)
    elif event_type == "message:sent":
        # v4.x outbound-send notification (CR-0008). Subscribed so the bridge's
        # delivery stats stay accurate; intentionally not wired to a refresh or HA
        # event -- it carries no roster/health/drift signal this integration acts on.
        _LOGGER.debug("Bridge message sent: %s", event_data)

    return Response(status=200)


def _iter_coordinators(hass: HomeAssistant):
    """Yield every entry's coordinator that supports webhook pushes."""
    for entry_data in hass.data.get(DOMAIN, {}).values():
        if not isinstance(entry_data, dict):
            continue
        coordinator = entry_data.get("coordinator")
        if coordinator is not None:
            yield coordinator
