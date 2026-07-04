<!--
Template: Bug Report (Streamlined)
File: sdlc-studio/bugs/BG{NNNN}-{slug}.md
Status values: See reference-outputs.md
Related: help/bug.md, reference-bug.md
-->
# BG0013: `extract_response_text` raises `AttributeError` on a malformed `choices` payload — escapes every `except BridgeError` handler

> **Status:** Open
> **Severity:** Low
> **Priority:** P3
> **Reporter:** Code + security review (RV-requested, 2026-07-04)
> **Assignee:** —
> **Created:** 2026-07-04
> **Verification depth:** functional

## Summary

The fast path in `helpers.extract_response_text` (helpers.py:104-110) does `choices[0].get("message", {})` after checking only that `choices` is a non-empty **list** — not that `choices[0]` is a dict. A bridge response of `{"choices": ["oops"]}` (or `[null]`, `[42]`) raises `AttributeError`. Every caller wraps the call in `except BridgeError` only (conversation.py:811, services.py:148, or not at all in ai_task.py:135), so a malformed bridge payload turns into an unhandled exception: the voice user gets HA's generic "unexpected error" instead of the friendly `ERROR_MESSAGES` text, and the service/AI-task call fails with a stack trace. The rest of `extract_response_text` is scrupulously defensive; this is the one unguarded spot at the bridge trust boundary.

**Verify:** `extract_response_text({"choices": ["oops"]})` and `extract_response_text({"choices": [None]})` return `None` without raising (falls through to the generic traversal).

## Affected Area

- **Component:** `helpers.py` (`extract_response_text` fast path); consumers `conversation.py`, `services.py`, `ai_task.py`
- **Origin:** pre-EP0007 response extraction, kept through the v4.36 realignment

## Environment

- **Version:** 0.11.0; requires a malformed/adversarial bridge response to trigger

---

## Reproduction Steps

1. Have the bridge (or anything terminating its TLS) return `{"choices": ["text"]}` for a chat completion.
2. Speak any utterance to the conversation entity.

## Expected Behaviour

Extraction fails soft (returns `None`), the turn degrades to an empty/friendly response, and no stack trace is logged.

## Actual Behaviour

`AttributeError: 'str' object has no attribute 'get'` propagates out of `_async_handle_message` / the service handler.

---

## Root Cause Analysis

Missing `isinstance(choices[0], dict)` guard in the `_depth == 0` fast path.

## Fix Description

_(to fill on fix)_ Guard `choices[0]` with `isinstance(..., dict)`; on mismatch fall through to the priority-key traversal, which already handles arbitrary shapes.

### Files Modified

| File | Change |
|------|--------|
| — | — |

---

## Verification

- [ ] Fix verified in development (unit)

**Verified by:** —
**Verification date:** —
**Verification depth:** functional

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-07-04 | Code + security review | Found auditing trust-boundary parsing |
