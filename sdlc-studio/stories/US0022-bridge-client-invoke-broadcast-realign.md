# US0022: Re-align bridge client to v4.36 `tools.invoke` + `broadcast`

> **Status:** Proposed
> **Epic:** [EP0007: Bridge v4.36 + Modern HA Re-Alignment](../epics/EP0007-bridge-v436-modern-ha-realignment.md)
> **Owner:** Darren Benson
> **Created:** 2026-06-01

## User Story

**As a** Home Assistant operator
**I want** the `invoke_tool` and `broadcast` services to work against the v4.36 bridge
**So that** tool invocation and fleet broadcasts stop failing with 400 errors

## User Story Context

Two confirmed, independent, self-contained request/response breaks (G6, G5) that fail the `invoke_tool` and `broadcast` services regardless of the actuation decision — fast wins. `client.invoke_tool` posts `{agent_id, tool_name, args}` but the bridge reads `body.agent`/`body.tool` and 400s; `/v1/broadcast` requires `{messages:[{role,content}], tags}` (HA sends `{message:<str>}`), `requireTags` defaults true so a tagless broadcast 400s, and the bridge returns `responses` as an object keyed by `agentId` while `services.py` treats it as a list.

## Acceptance Criteria

### AC1: `invoke_tool` request field names re-aligned
- **Given** `client.invoke_tool`
- **When** called
- **Then** it POSTs `{agent, tool, args}` (not `agent_id`/`tool_name`) and the bridge returns `ok:true`
- **Verify:** `pytest` unit asserting the `invoke_tool` body keys are `{agent, tool, args}`

### AC2: `broadcast` request shape + tags + responses-object handling
- **Given** `client.broadcast(message, tags)`
- **When** called
- **Then** it POSTs `{messages:[{role:'user',content:message}], tags}` with a non-empty `tags` array (default e.g. `['operator']`), and `services` parses the `responses` OBJECT keyed by `agentId` (not a list)
- **Verify:** `pytest` asserting the broadcast body has a `messages` array + non-empty `tags` and that a dict-shaped `responses` payload is iterated by key

## Scope

### In Scope
- `client.invoke_tool` request field rename (`agent`/`tool`)
- `client.broadcast` request shape: `messages[]` + non-empty `tags`
- `services.py` parsing of the `responses` object keyed by `agentId`

### Out of Scope
- The actuation tool-call loop (US0027)
- Any change to the `args` key (still accepted)

## Technical Notes

- `args` remains the accepted key for `invoke_tool`; only the request field names break.
- Default broadcast `tags` to a sensible non-empty value (e.g. `['operator']`) because `requireTags` defaults true on the bridge.
- The broadcast `responses` is an object keyed by `agentId`; iterate by key rather than `.get('responses', [])`.

## Dependencies

### Story Dependencies

| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| — | — | No story dependency (P0 fast win) | — |

## Estimation

**Story Points:** 3
**Complexity:** Low

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-06-01 | Claude | Initial story for EP0007 (CR-0002 redesign) |
