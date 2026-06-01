# US0023: Fix SSE streaming delta/terminal parsing + fail-safe error handling

> **Status:** Proposed
> **Epic:** [EP0007: Bridge v4.36 + Modern HA Re-Alignment](../epics/EP0007-bridge-v436-modern-ha-realignment.md)
> **Owner:** Darren Benson
> **Created:** 2026-06-01

## User Story

**As a** voice satellite user
**I want** streamed agent responses to actually arrive and real errors to surface
**So that** the streaming voice path produces output instead of silently yielding nothing

## User Story Context

G7: the bridge emits `event:message data:{text}` + `event:done`, while HA's `_iter_sse` parses `choices[0].delta.content` + a `data:[DONE]` sentinel the bridge never sends, so every delta is skipped and the stream yields nothing. The stream path also discards `tool_calls` and swallows all exceptions to a debug log on the exact voice path the component exists to serve. Until actuation can ride the stream, the safe near-term is to accept the `{text}` shape and stop swallowing real errors (or disable the streaming opt-in).

## Acceptance Criteria

### AC1: Parse the v4.36 `{text}` delta shape
- **Given** a bridge SSE line `event:message data:{"text":"hi"}`
- **When** `_iter_sse` parses it
- **Then** it yields `'hi'`
- **Verify:** `pytest` feeding a `{text}` SSE fixture asserts the delta is yielded

### AC2: Terminate on `event:done` or socket close (no `[DONE]` reliance)
- **Given** an `event:done` frame or a socket close
- **When** encountered
- **Then** iteration stops cleanly without relying on `data:[DONE]`
- **Verify:** `pytest` asserting the `done` frame terminates iteration

### AC3: Fail-safe error handling (no silent swallow)
- **Given** a non-`CancelledError` exception on the stream path
- **When** it occurs
- **Then** it is logged at error level (not silently swallowed to debug) and falls back to non-streaming
- **Verify:** `pytest` asserting a raised `RuntimeError` is logged and triggers fallback rather than a bare debug swallow

## Scope

### In Scope
- `_iter_sse` parsing of `event:message data:{text}` deltas
- `event:done` / socket-close termination
- Error logging + fallback to non-streaming on the stream path

### Out of Scope
- Streaming `tool_calls` (deferred until actuation rides the stream; documented in US0030)
- Streaming for non-voice/text requests

## Technical Notes

- The streaming branch fires only when `is_voice` AND `enable_tools` is disabled (default `enable_tools=True`), so it is dormant under default config — it bites operators who disable tool calls for voice.
- Catch `CancelledError` separately; everything else logs at error and falls back rather than swallowing to debug.

## Dependencies

### Story Dependencies

| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| — | — | No story dependency (P0 fast win) | — |

## Estimation

**Story Points:** 3
**Complexity:** Medium

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-06-01 | Claude | Initial story for EP0007 (CR-0002 redesign) |
