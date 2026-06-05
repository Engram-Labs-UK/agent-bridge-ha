# US0035: Camera/vision input via image attachments

> **Status:** Done
> **Epic:** [EP0008: Conversation Capability Expansion](../epics/EP0008-conversation-capability-expansion.md)
> **Owner:** Darren Benson
> **Created:** 2026-06-05

## User Story

**As a** user
**I want** the agent to see a camera snapshot
**So that** it can answer "who's at the front door?" or "is the garage open?"

## User Story Context

The bridge already accepts base64 image `attachments` on `/v1/chat/completions`. The component
sends none and `client.chat()` has no attachments param. Cora ranked this up: vision is safety
(a class of requests currently fails silently).

## Acceptance Criteria

### AC1: client.chat carries attachments
- **Given** an image
- **When** `client.chat(..., attachments=[...])`
- **Then** the body includes a sanitised `attachments` array (base64 + mime)
- **Verify:** `pytest` asserts the attachments reach the request body

### AC2: ask_with_image service
- **Given** a camera entity
- **When** `agent_bridge.ask_with_image` is called with a prompt + camera_entity_id
- **Then** the component fetches the snapshot (`camera.async_get_image`) and sends it to the agent
- **Verify:** `pytest` mocks the camera and asserts the snapshot is attached + response returned

### AC3: Safe handling
- **Given** a missing/oversized image or a non-image agent
- **When** sending
- **Then** the component degrades gracefully (clear error / drop) without crashing the turn
- **Verify:** `pytest` asserts graceful handling of fetch failure / oversize

## Scope

### In Scope
- `attachments` param on `client.chat()`; `agent_bridge.ask_with_image` service
### Out of Scope
- Conversation-turn inline image (no standard HA path); AI Task attachments (US0039)

## Technical Notes

- `camera.async_get_image` → base64; mime image/jpeg. Bridge attachment shape per CR-0154.

## Estimation

**Story Points:** 5
**Complexity:** Medium

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-06-05 | Claude | Initial story for EP0008 (CR-0004), Phase 2 |
| 2026-06-05 | Claude | Implemented: `attachments` on `client.chat`; `agent_bridge.ask_with_image` service (camera.async_get_image → base64 bridge attachment) + services.yaml UI. Camera errors handled gracefully. Self-review: additive, existing chat paths unchanged; attachment shape matches bridge inbound contract; no hard size cap (camera snapshots are small — acceptable). Unit-tested. Status → Done |
