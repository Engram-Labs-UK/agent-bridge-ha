# US0038: Agent → Telegram camera snapshot (+ bridge sendPhoto)

> **Status:** Proposed
> **Epic:** [EP0008: Conversation Capability Expansion](../epics/EP0008-conversation-capability-expansion.md)
> **Owner:** Darren Benson
> **Created:** 2026-06-05

## User Story

**As a** user
**I want** the agent to send me a camera snapshot on Telegram
**So that** I can see the front door / garage from chat

## User Story Context

Not possible today: the bridge Telegram client (`src/telegram/client.ts`) has only
`sendMessage`/`sendChatAction` — no `sendPhoto`; inbound media works, outbound image does not.
Needs a co-requisite agent-bridge PR. OpenClaw agents (Cora) have a `camera_snap`+`notify`
shortcut for cameras they can reach.

## Acceptance Criteria

### AC1: HA snapshot-send service
- **Given** a camera entity + target
- **When** `agent_bridge.send_image` (or extend ask_with_image) is called
- **Then** HA fetches the snapshot and hands it to the bridge as an outbound attachment
- **Verify:** `pytest` asserts the snapshot is sent as an outbound attachment

### AC2: Bridge delivers image to Telegram (co-requisite PR)
- **Given** an agent reply carrying an image attachment bound to a Telegram channel
- **When** the bridge dispatches
- **Then** the Telegram client sends it via `sendPhoto`/`sendDocument`
- **Verify:** bridge `vitest` asserts `sendPhoto` is called with the attachment (CI)

### AC3: Graceful when bridge lacks support
- **Given** an un-upgraded bridge
- **When** sending
- **Then** the HA side degrades gracefully (clear message), no crash
- **Verify:** `pytest` asserts graceful degradation

## Scope

### In Scope
- HA: snapshot-send service. Bridge PR: `sendPhoto`/`sendDocument` + outbound-attachment plumbing
### Out of Scope
- Video; arbitrary file types beyond image/document

## Technical Notes

- Bridge: add to `src/telegram/client.ts` + wire an agent reply's image attachment to the
  AgentBot outbound path. HA: `camera.async_get_image` → outbound attachment.

## Estimation

**Story Points:** 8
**Complexity:** High

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-06-05 | Claude | Initial story for EP0008 (CR-0004), Phase 5 |
