<!--
Template: Bug Report (Streamlined)
File: sdlc-studio/bugs/BG{NNNN}-{slug}.md
Status values: See reference-outputs.md
Related: help/bug.md, reference-bug.md
-->
# BG0014: Webhook handler raises on valid-JSON-but-non-object payloads

> **Status:** Open
> **Severity:** Low
> **Priority:** P3
> **Reporter:** Code + security review (RV-requested, 2026-07-04)
> **Assignee:** —
> **Created:** 2026-07-04
> **Verification depth:** functional

## Summary

`webhook._handle_webhook` (webhook.py:103-110) guards against invalid JSON (`except` around `request.json()` → 400) but then calls `payload.get("event")` without checking that the parsed value is a dict. A POST of `[1,2,3]`, `"str"`, or `42` — valid JSON — raises `AttributeError` inside the handler. The webhook endpoint is unauthenticated by design (the id is the secret), so this is a trivially reachable unhandled-exception path for anyone who learns the id; it should be the same clean 400 as malformed JSON. (Value-level validation of the payload — e.g. the `status` push — is the separate hardening CR-0014.)

**Verify:** POSTing bodies `[1,2,3]`, `"x"`, and `42` to the webhook each returns HTTP 400 with no exception logged.

## Affected Area

- **Component:** `webhook.py` (`_handle_webhook`)
- **Origin:** Phase 2 webhook support (US0024)

## Environment

- **Version:** 0.11.0

---

## Reproduction Steps

1. `curl -X POST -H 'Content-Type: application/json' -d '[1,2,3]' http://ha:8123/api/webhook/<id>`

## Expected Behaviour

HTTP 400 ("Invalid webhook payload received"), same as unparseable JSON.

## Actual Behaviour

`AttributeError: 'list' object has no attribute 'get'` escapes the handler and is logged as an error by HA's webhook view.

---

## Root Cause Analysis

The dict-shape assumption is implicit; only the JSON-parse failure mode is handled.

## Fix Description

_(to fill on fix)_ After parsing, `if not isinstance(payload, dict): return Response(status=400)` (or fold into the existing except by validating inside the try).

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
| 2026-07-04 | Code + security review | Found auditing the unauthenticated webhook surface (with CR-0014) |
