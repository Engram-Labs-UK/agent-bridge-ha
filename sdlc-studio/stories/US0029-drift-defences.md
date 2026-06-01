# US0029: Drift defences — agent-context awareness, version pin, CI vs current HA

> **Status:** Proposed
> **Epic:** [EP0007: Bridge v4.36 + Modern HA Re-Alignment](../epics/EP0007-bridge-v436-modern-ha-realignment.md)
> **Owner:** Darren Benson
> **Created:** 2026-06-01

## User Story

**As a** maintainer of agent-bridge-ha
**I want** silent bridge/HA drift converted into operator-visible signal
**So that** the integration never again drifts v3.1→v4.36 unnoticed

## User Story Context

G13/G16: the component drifted v3.1→v4.36 silently because it reads none of the bridge's machine-readable changelog (`/v1/agent-context`, `/v1/welcome` — `notable_capabilities`/`knownIssues`/`deprecations`) and tracks HA model fields via `getattr` reflection with no tested-version pin. This converts silent drift into operator-visible signal: an HA repair issue on bridge-version/deprecation drift, typed field reads, and CI against a current HA core.

## Acceptance Criteria

### AC1: Agent-context drift → HA repair issue
- **Given** setup and a `bridge:upgraded` event (US0024)
- **When** fired
- **Then** the component fetches `/v1/agent-context`, compares the bridge version + `notable_capabilities`/`deprecations` against the integration's tested baseline, and raises an HA repair issue when they move past it
- **Verify:** `pytest` asserting a repair issue is raised when agent-context reports a deprecation past baseline

### AC2: Typed field reads (no `getattr` reflection)
- **Given** `ConversationInput` fields
- **When** read
- **Then** `satellite_id`/`extra_system_prompt` come from the typed input / `chat_log.llm_context` (not `getattr` reflection)
- **Verify:** `grep` asserting `getattr(user_input, ...)` reflection is removed from the handler

### AC3: Pinned + CI-tested HA version
- **Given** the repo
- **Then** `manifest`/`hacs` pin a documented tested HA version and CI runs the test suite against a current HA core
- **Verify:** CI config runs against a pinned current HA

## Scope

### In Scope
- `/v1/agent-context` fetch on `bridge:upgraded` + baseline comparison
- HA repair issue on version/deprecation drift past baseline
- Typed `ConversationInput` field reads (drop `getattr` reflection)
- `manifest`/`hacs` HA-version pin + CI matrix against current HA core

### Out of Scope
- The webhook routing that fires `bridge:upgraded` (US0024)
- Documentation of the boundary/contract (US0030)

## Technical Notes

- Depends on the `bridge:upgraded` HA event routed by US0024.
- The immediate `getattr` risk is the `satellite_id` path (silent `None` on a field rename).
- HA conversation/LLM API is itself a moving target — the CI matrix is what prevents re-drift.

## Dependencies

### Story Dependencies

| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| US0024 | Event | `bridge:upgraded` HA event to trigger agent-context fetch | Proposed |

## Estimation

**Story Points:** 5
**Complexity:** Medium

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-06-01 | Claude | Initial story for EP0007 (CR-0002 redesign) |
