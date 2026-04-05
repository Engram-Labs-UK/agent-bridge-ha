# US0018: Webhook Integration

> **Status:** Done
> **Epic:** [EP0005: Real-Time & Broadcast](../epics/EP0005-realtime-and-broadcast.md)
> **Owner:** Darren Benson
> **Created:** 2026-04-05

## User Story

**As a** the integration
**I want** real-time agent health updates from the bridge via webhooks
**So that** HA reacts instantly to agent outages instead of waiting for the next poll

## Acceptance Criteria

### AC1: Webhook Registration
- **Given** the integration is set up and bridge is reachable
- **When** async_setup_entry runs
- **Then** a webhook is registered with the bridge via `POST /v1/webhooks` subscribing to `agent:health-changed`, and the HA webhook ID is stored

### AC2: Webhook Event Handling
- **Given** a webhook is registered
- **When** the bridge sends a health-changed event to the HA webhook endpoint
- **Then** the coordinator data is updated immediately without waiting for the next poll

### AC3: Webhook Refresh on Restart
- **Given** HA restarts and a previous webhook ID is stored
- **When** async_setup_entry runs
- **Then** the webhook registration is refreshed (re-registered)

### AC4: Graceful Fallback
- **Given** webhook registration fails (network, bridge doesn't support it)
- **When** the integration starts
- **Then** polling continues normally, a warning is logged, and no error is raised

### AC5: Webhook Unregistration
- **Given** the integration is being unloaded
- **When** async_unload_entry runs
- **Then** the webhook is unregistered via `DELETE /v1/webhooks/:id`

## Scope

### In Scope
- New `webhook.py` module with HA webhook handler
- `register_webhook()` and `unregister_webhook()` methods in BridgeClient
- Webhook lifecycle in `__init__.py` (register on setup, unregister on unload)
- Coordinator accepts pushed data via `async_push_webhook_data()`

### Out of Scope
- Replacing polling (webhooks supplement, not replace)
- Per-agent webhook subscriptions

## Technical Notes

- Uses HA's `webhook.async_register` for the inbound endpoint
- Webhook callback URL: `{ha_external_url}/api/webhook/{webhook_id}`
- Bridge webhook API: `POST /v1/webhooks` with `{"url": "...", "events": ["agent:health-changed"]}`
- Store webhook_id in hass.data for unregistration

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| Bridge doesn't support webhooks (404 on POST) | Log warning, continue with polling only |
| HA has no external URL configured | Skip webhook registration, log info |
| Bridge sends malformed webhook payload | Log warning, ignore event |
| Webhook unregistration fails on unload | Log warning, don't block unload |

## Dependencies

### Story Dependencies

| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| US0005 | Service | DataUpdateCoordinator | Done |
| US0002 | Service | BridgeClient | Done |

### External Dependencies

| Dependency | Type | Status |
|------------|------|--------|
| Bridge webhook API (POST /v1/webhooks) | API | Assumed available |

## Estimation

**Story Points:** 3
**Complexity:** Medium

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-04-05 | Claude | Initial story for Phase 2 implementation |
