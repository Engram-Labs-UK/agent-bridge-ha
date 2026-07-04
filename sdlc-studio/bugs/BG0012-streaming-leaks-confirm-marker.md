<!--
Template: Bug Report (Streamlined)
File: sdlc-studio/bugs/BG{NNNN}-{slug}.md
Status values: See reference-outputs.md
Related: help/bug.md, reference-bug.md
-->
# BG0012: Streaming path speaks the `[confirm:LEVEL]` marker aloud and stores it unstripped in the ChatLog

> **Status:** Open
> **Severity:** Medium
> **Priority:** P2
> **Reporter:** Code + security review (RV-requested, 2026-07-04)
> **Assignee:** —
> **Created:** 2026-07-04
> **Verification depth:** functional

## Summary

US0036's confirm-before-actuate contract says HA **strips** the `[confirm:LEVEL]` marker from the spoken text. The non-streaming path honours this (`_parse_confirm_marker` runs before `async_add_assistant_content_without_tools`). The streaming path (US0033, `CONF_ENABLE_STREAMING`) does not: bridge deltas are piped verbatim into `chat_log.async_add_delta_content_stream(...)`, which is exactly the stream Assist consumes for streaming TTS — so the satellite speaks "*left bracket confirm colon high right bracket …*". The marker is only stripped afterwards from the local `text` variable (conversation.py:793-799); the ChatLog's stored assistant turn keeps the raw marker, so `_messages_from_chat_log` also replays it to the bridge as history on every later turn in the conversation.

**Verify:** with streaming enabled and a reply of `[confirm:high] Shall I unlock the door?`, (a) no chunk yielded to `chat_log.async_add_delta_content_stream` contains `[confirm:`, (b) the stored assistant ChatLog content is `Shall I unlock the door?`, and (c) `awaiting_confirmation` is still `True` with `severity == "high"` in both fired events.

## Affected Area

- **Component:** `conversation.py` (`_to_delta_stream`, streaming branch of `_async_handle_message`)
- **Origin:** US0033 (streaming) × US0036 (confirm markers) — the two features never met in a test; `tests/test_streaming.py` has no confirm-marker case.

## Environment

- **Version:** 0.11.0 (streaming is opt-in, default off — which caps the severity)

---

## Reproduction Steps

1. Enable **Stream replies** in options (experimental toggle).
2. Expose a `lock.*` entity; ask the agent to unlock the door.
3. Agent replies `[confirm:high] Do you want me to unlock the front door?` as SSE deltas.

## Expected Behaviour

The marker is stripped before any delta reaches TTS/ChatLog; severity is surfaced via the events; stored history is clean.

## Actual Behaviour

The marker is spoken aloud by the satellite, persists in the ChatLog assistant turn, and is re-sent to the bridge as conversation history on subsequent turns.

---

## Root Cause Analysis

`_to_delta_stream` forwards raw deltas with no marker handling; the strip (`_parse_confirm_marker`) runs only on the assembled `text` copy after the stream completes, which affects the `intent_response` speech and events but not the already-emitted delta stream or the ChatLog content.

## Fix Description

_(to fill on fix)_ Suggested approach: buffer the first chunk(s) in `_to_delta_stream` until either the `_CONFIRM_MARKER` regex matches (strip, record severity, then yield the remainder) or enough text has arrived to rule a marker out, then pass through. The recorded severity feeds the existing event/continue logic; the ChatLog then stores clean text for free.

### Files Modified

| File | Change |
|------|--------|
| — | — |

---

## Verification

- [ ] Fix verified in development (unit)
- [ ] Live: streamed confirm reply is spoken without the marker

**Verified by:** —
**Verification date:** —
**Verification depth:** functional

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-07-04 | Code + security review | Found reviewing the US0033/US0036 interaction; no test covers streaming + confirm |
