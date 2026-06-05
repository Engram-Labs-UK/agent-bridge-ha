# US0033: Response streaming to TTS (deltas)

> **Status:** Review — component-side done (opt-in, default off); live TTS validation pending
> **Epic:** [EP0008: Conversation Capability Expansion](../epics/EP0008-conversation-capability-expansion.md)
> **Owner:** Darren Benson
> **Created:** 2026-06-05

## User Story

**As a** voice user
**I want** the agent's reply to start speaking before it is fully generated
**So that** long answers feel responsive

## User Story Context

`client.chat_stream()` + `conversation._stream_chat()` already parse the bridge SSE delta format
but are dormant — the live handler uses non-streaming `client.chat()`. Wire streaming into HA's
`chat_log.async_add_delta_content_stream(agent_id, stream)` (Context7-confirmed), within the
existing SSE transport only (Cora: don't add a transport layer for this).

## Acceptance Criteria

### AC1: Stream deltas into ChatLog
- **Given** a turn
- **When** the agent streams a reply over SSE
- **Then** the handler feeds deltas via `chat_log.async_add_delta_content_stream` and the final
  speech equals the assembled text
- **Verify:** `pytest` with a fake streaming client asserts deltas are added and final text matches

### AC2: Fail-safe fallback to non-streaming
- **Given** a streaming error (connection/auth/empty)
- **When** streaming fails
- **Then** the handler falls back to non-streaming `client.chat()` and still returns a result
- **Verify:** `pytest` simulates a streaming error and asserts the non-streaming path runs

### AC3: Streaming is opt-in/safe with caller_context + session
- **Given** US0032 channel key + caller_context
- **When** streaming
- **Then** channel/caller_context are sent identically to the non-streaming path
- **Verify:** `pytest` asserts request parity between stream and non-stream paths

## Scope

### In Scope
- Wire `_stream_chat`/`chat_stream` into the handler with `async_add_delta_content_stream`
- Fail-safe fallback; keep request shape identical

### Out of Scope
- TTS audio chunking beyond what HA's ChatLog streaming provides
- Any new transport

## Technical Notes

- Touchpoints: `conversation.py` handler. Reuse `client.chat_stream` (SSE parser exists).
- Only adopt if it stays within existing SSE (no protocol change).

## Estimation

**Story Points:** 3
**Complexity:** Medium

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-06-05 | Claude | Initial story for EP0008 (CR-0004), Phase 1b |
| 2026-06-05 | Claude | Implemented opt-in streaming (`CONF_ENABLE_STREAMING`, default off): `_to_delta_stream` adapts bridge text deltas to HA's `async_add_delta_content_stream`; fallback to non-streaming on any error. Review fix: content-length guard prevents double-append on empty/partial streams. Adapter + fallback unit-tested; streaming integration tests CI-gated. Status → Review (live TTS validation pending) |
