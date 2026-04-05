"""Execute HA services from agent tool_call responses."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from homeassistant.core import HomeAssistant

from .const import DEFAULT_TOOL_TIMEOUT, EVENT_TOOL_INVOKED

_LOGGER = logging.getLogger(__name__)


def _parse_tool_arguments(raw_args: str | dict[str, Any]) -> dict[str, Any]:
    """Parse tool call arguments from string or dict."""
    if isinstance(raw_args, dict):
        return raw_args
    if isinstance(raw_args, str):
        try:
            parsed = json.loads(raw_args)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


async def _execute_single_service(
    hass: HomeAssistant,
    domain: str,
    service: str,
    entity_id: str,
    *,
    service_data: dict[str, Any] | None = None,
    timeout: float = DEFAULT_TOOL_TIMEOUT,
) -> dict[str, Any]:
    """Execute a single HA service call with timeout."""
    start = time.monotonic()

    try:
        target = {"entity_id": entity_id}
        await asyncio.wait_for(
            hass.services.async_call(
                domain,
                service,
                service_data=service_data or {},
                target=target,
                blocking=True,
            ),
            timeout=timeout,
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        return {
            "success": True,
            "entity_id": entity_id,
            "service": f"{domain}.{service}",
            "duration_ms": duration_ms,
        }
    except TimeoutError:
        return {
            "success": False,
            "entity_id": entity_id,
            "error": f"Service call timed out after {timeout}s",
        }
    except Exception as err:  # noqa: BLE001
        return {
            "success": False,
            "entity_id": entity_id,
            "error": str(err),
        }


async def execute_tool_call(
    hass: HomeAssistant,
    tool_call: dict[str, Any],
    exposed_entity_ids: set[str],
) -> dict[str, Any]:
    """Execute a single tool_call and return the result.

    Validates entity_id against the exposure list before execution.
    Returns JSON result (never raises).
    """
    function = tool_call.get("function", {})
    tool_name = function.get("name", "")
    args = _parse_tool_arguments(function.get("arguments", "{}"))

    if tool_name == "execute_service":
        return await _execute_service(hass, args, exposed_entity_ids)

    if tool_name == "execute_services":
        return await _execute_services_batch(hass, args, exposed_entity_ids)

    return {"success": False, "error": f"Unknown tool: {tool_name}"}


async def _execute_service(
    hass: HomeAssistant,
    args: dict[str, Any],
    exposed_entity_ids: set[str],
) -> dict[str, Any]:
    """Execute a single execute_service tool call."""
    domain = args.get("domain", "")
    service = args.get("service", "")
    entity_id = args.get("entity_id", "")
    service_data = args.get("service_data", {})

    # Support target dict as alternative to entity_id
    target = args.get("target", {})
    if not entity_id and isinstance(target, dict):
        entity_id = target.get("entity_id", "")

    if not domain or not service:
        return {"success": False, "error": "Missing domain or service"}

    if not entity_id:
        return {"success": False, "error": "Missing entity_id"}

    if entity_id not in exposed_entity_ids:
        return {
            "success": False,
            "error": f"Entity {entity_id} not found in exposed entities",
        }

    result = await _execute_single_service(
        hass, domain, service, entity_id, service_data=service_data
    )

    # Fire event
    hass.bus.async_fire(
        EVENT_TOOL_INVOKED,
        {
            "tool_name": f"{domain}.{service}",
            "entity_id": entity_id,
            "status": "ok" if result["success"] else "error",
            "duration_ms": result.get("duration_ms", 0),
        },
    )

    return result


async def _execute_services_batch(
    hass: HomeAssistant,
    args: dict[str, Any],
    exposed_entity_ids: set[str],
) -> dict[str, Any]:
    """Execute batched service calls in parallel (ADR-005)."""
    calls = args.get("calls", [])
    if not isinstance(calls, list) or not calls:
        return {"success": False, "error": "Missing or empty calls list"}

    tasks = []
    for call_args in calls:
        if not isinstance(call_args, dict):
            continue
        tasks.append(_execute_service(hass, call_args, exposed_entity_ids))

    if not tasks:
        return {"success": False, "error": "No valid service calls in batch"}

    results = await asyncio.gather(*tasks, return_exceptions=True)

    processed: list[dict[str, Any]] = []
    for result in results:
        if isinstance(result, Exception):
            processed.append({"success": False, "error": str(result)})
        else:
            processed.append(result)

    all_success = all(r.get("success", False) for r in processed)
    return {
        "success": all_success,
        "results": processed,
    }
