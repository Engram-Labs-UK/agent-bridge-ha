# US0027: Restore actuation via HA Assist LLM API + fail-closed exposure

> **Status:** Proposed
> **Epic:** [EP0007: Bridge v4.36 + Modern HA Re-Alignment](../epics/EP0007-bridge-v436-modern-ha-realignment.md)
> **Owner:** Darren Benson
> **Created:** 2026-06-01

## User Story

**As a** Home Assistant voice user
**I want** "turn on the lights" to actually actuate a device again
**So that** the reactive home-control path stops being structurally inert (agents reply but never act)

## User Story Context

G1/G4: the load-bearing fix. Per the CR-0002 decision (Option A), delegate entity context + validated tools to HA's Assist LLM API via `chat_log.async_provide_llm_data()` and `llm.Tool` calls (preferred — converges with the working DBee proactive MCP path and removes cross-repo schema risk). The fallback fork (Option B) sends `tools[]` AND lands a co-requisite `agent-bridge` bridge CR. This story also fixes the fail-open exposure bare-except (`exposure.py:125-127` returns True on import failure, exposing ALL entities).

## Acceptance Criteria

### AC1: Actuation restored (per chosen strategy)
- **Given** Option A, **When** a turn needs actuation, **Then** the entity calls `chat_log.async_provide_llm_data()` with the Assist API (`api_prompt` + exposed context + `llm.Tool`), and a tool call results in a validated hass intent/service call with the result flowing back through `ChatLog`; the bespoke `execute_service` path is retained only as a fallback for agents that cannot consume the schema
- **Given** Option B, **When** a turn needs actuation, **Then** HA sends `tools[]` in the chat body AND the bridge (per the linked CR) returns `tool_calls` + `finish_reason:'tool_calls'`, which `extract_tool_calls` parses and `tool_executor` executes
- **Verify:** `pytest` simulating a tool-calling turn asserts an HA service/intent is actually invoked for a 'turn on the lights' utterance

### AC2: Exposure fails closed
- **Given** an entity-exposure import failure
- **When** `_is_entity_exposed` runs
- **Then** it fails CLOSED (skip the entity), never expose-all
- **Verify:** `pytest` asserting exposure fails closed on `ImportError`

## Scope

### In Scope
- Actuation via the chosen strategy (Option A preferred: HA Assist LLM API / `llm.Tool`)
- Result flow back through `ChatLog`
- Fail-closed `_is_entity_exposed` on import failure
- `exposure.py`/`tool_executor.py` retained as fallback only (per Option A)

### Out of Scope
- Per-agent TTS voice selection / wake-word training
- New bridge features beyond the Option B `tools[]`/`tool_calls` passthrough (filed separately in `agent-bridge`)
- Replacing the proactive MCP Server path (DBee) — boundary documented in US0030, not altered here

## Technical Notes

- Live-agent consult mandatory: confirm Cora/Spanners can drive `llm.Tool` before freezing (Option A may need harness-side wiring for heterogeneous agents).
- Fail-closed must be a deliberate, logged fallback — not silent expose-all OR silent expose-none.
- Option B requires a cross-repo `agent-bridge` CR (`tools[]`/`tool_calls` through `chat.ts` → `RouterRequest`/`SendOptions` → http-openai adapter); track across both repos.

## Dependencies

### Story Dependencies

| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| US0026 | Platform | `_async_handle_message` + `ChatLog` to wire `async_provide_llm_data()` | Proposed |

## Estimation

**Story Points:** 8
**Complexity:** High

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-06-01 | Claude | Initial story for EP0007 (CR-0002 redesign) |
