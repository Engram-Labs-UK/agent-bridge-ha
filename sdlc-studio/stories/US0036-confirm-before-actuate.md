# US0036: Confirm-before-actuate (pendingAction + timeout + severity)

> **Status:** Proposed
> **Epic:** [EP0008: Conversation Capability Expansion](../epics/EP0008-conversation-capability-expansion.md)
> **Owner:** Darren Benson
> **Created:** 2026-06-05

## User Story

**As a** user
**I want** the agent to confirm before safety-relevant actions and remember the pending action
**So that** "unlock the front door" is gated and completes safely on "yes"

## User Story Context

Rides on US0032 session continuity. Cora's concrete needs: a `pendingAction`
`{actionId, tool, params, requestedAt, timeoutSec}` carried on the session; a persistent
thread across the confirm turn; standard timeouts (30 s voice / 5 min typed); and a `severity`
hint so HA can choose audio tone / visual emphasis.

## Acceptance Criteria

### AC1: Confirm turn keeps the conversation open
- **Given** a safety-relevant request (deny/confirm domain)
- **When** the agent returns a confirm question
- **Then** `continue_conversation` is true and the session/thread persists to the next turn
- **Verify:** `pytest` asserts continue_conversation + stable channel across the confirm turn

### AC2: Severity surfaced
- **Given** a confirm response carrying a severity hint
- **When** HA processes it
- **Then** severity is exposed (event/attribute) for tone/visual selection
- **Verify:** `pytest` asserts severity is parsed and surfaced

### AC3: Timeout window
- **Given** a pending confirm
- **When** the timeout elapses (30 s voice / 5 min typed)
- **Then** the pending action is treated as void on the HA side
- **Verify:** `pytest` with a controllable clock asserts void-after-timeout

## Scope

### In Scope
- continue_conversation on confirm; severity surfacing; timeout handling on the HA side
### Out of Scope
- Server-side enforcement of the action (agent self-actuates via /api/mcp, Option A)

## Technical Notes

- Most behaviour emerges from US0032 + existing `_detect_continuation` + safety prompt; HA adds
  severity surfacing + timeout bookkeeping. Validate end-to-end with the live agent.

## Estimation

**Story Points:** 5
**Complexity:** Medium

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-06-05 | Claude | Initial story for EP0008 (CR-0004), Phase 3 |
