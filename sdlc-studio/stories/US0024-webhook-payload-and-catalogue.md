# US0024: Webhook `agent:health-changed` payload + full event catalogue

> **Status:** Done
> **Epic:** [EP0007: Bridge v4.36 + Modern HA Re-Alignment](../epics/EP0007-bridge-v436-modern-ha-realignment.md)
> **Owner:** Darren Benson
> **Created:** 2026-06-01

## User Story

**As a** Home Assistant operator
**I want** real-time bridge webhooks to be handled and the full event catalogue subscribed
**So that** health changes and `bridge:upgraded` drift signals arrive without waiting on the 300s poll

## User Story Context

G11 + G10: the bridge `agent:health-changed` payload is `{agentId, healthy}` but `async_push_webhook_data` early-returns unless `'status'` is in the data, so every push is dropped and the real-time path degrades to 100% polling. Additionally, the bridge emits seven event types and HA registers only one — missing `bridge:upgraded`, the exact drift signal this audit is about.

## Acceptance Criteria

### AC1: Handle the `{agentId, healthy}` health-changed payload
- **Given** a push `{agentId, healthy:false}`
- **When** `async_push_webhook_data` runs
- **Then** it updates that agent's `healthy` flag + recomputes counts (or `request_refresh`) rather than no-opping
- **Verify:** `pytest` pushing `{agentId, healthy:false}` asserts coordinator state changes

### AC2: Subscribe to the full event catalogue incl. `bridge:upgraded`
- **Given** setup
- **When** the webhook is registered
- **Then** it subscribes to `agent:registered`/`unregistered`/`updated`/`health-changed`, `message:error` and `bridge:upgraded`, and routes each
- **Verify:** `pytest` asserting the `register_webhook` call lists all six+ event types

### AC3: Route `bridge:upgraded` to an HA event
- **Given** a `bridge:upgraded` event
- **When** received
- **Then** an HA event fires (feeding US0029 drift detection)
- **Verify:** `pytest` asserting `bridge:upgraded` is routed and fires an HA event

## Scope

### In Scope
- `async_push_webhook_data` handling of the `{agentId, healthy}` payload
- Webhook registration for all bridge event types
- Routing `bridge:upgraded` to an HA event for downstream drift detection

### Out of Scope
- The drift-detection consumer itself (US0029)
- Per-agent health-block enrichment (US0028)

## Technical Notes

- The current handler conflates per-agent health with bridge-status; separate them.
- `bridge:upgraded` is the drift signal the whole CR-0002 audit is about — it must be observed, not polled for.

## Dependencies

### Story Dependencies

| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| — | — | No story dependency (P0 fast win; feeds US0029) | — |

## Estimation

**Story Points:** 3
**Complexity:** Medium

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-06-01 | Claude | Initial story for EP0007 (CR-0002 redesign) |
| 2026-06-02 | Claude | R1 implemented + unit-tested (pytest green); status -> Done |
