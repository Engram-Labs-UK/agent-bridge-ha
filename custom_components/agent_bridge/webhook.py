"""Webhook handler for real-time bridge events."""

from __future__ import annotations

import logging

from aiohttp.web import Request, Response
from homeassistant.components import webhook
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_register_webhook(
    hass: HomeAssistant,
    entry_id: str,
) -> str | None:
    """Register a webhook with HA and return the webhook ID."""
    webhook_id = webhook.async_generate_id()

    webhook.async_register(
        hass,
        DOMAIN,
        "Agent Bridge",
        webhook_id,
        _handle_webhook,
    )

    _LOGGER.info("Registered HA webhook: %s", webhook_id)
    return webhook_id


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
        result = await client.register_webhook(callback_url, ["agent:health-changed"])
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
        _LOGGER.info("Unregistered HA webhook: %s", webhook_id)


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

    event_type = payload.get("event")
    event_data = payload.get("data", {})

    _LOGGER.debug("Webhook event: %s", event_type)

    if event_type == "agent:health-changed":
        for entry_data in hass.data.get(DOMAIN, {}).values():
            if not isinstance(entry_data, dict):
                continue
            coordinator = entry_data.get("coordinator")
            if coordinator and hasattr(coordinator, "async_push_webhook_data"):
                await coordinator.async_push_webhook_data(event_data)

    return Response(status=200)
