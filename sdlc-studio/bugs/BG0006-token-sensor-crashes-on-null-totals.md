<!--
Template: Bug Report (Streamlined)
File: sdlc-studio/bugs/BG{NNNN}-{slug}.md
Status values: See reference-outputs.md
Related: help/bug.md, reference-bug.md
-->
# BG0006: Usage token sensor raises on null/non-numeric totals; 0-vs-None; dead translation_key

> **Status:** Fixed
> **Severity:** High
> **Priority:** P2
> **Reporter:** Claude (RV0006 code review)
> **Assignee:** —
> **Created:** 2026-06-09
> **Verification depth:** functional

## Summary

`AgentTokensSensor.native_value` (CR-0009) sums `int(totals.get("totalIn", 0)) + int(totals.get("totalOut", 0))` with **no numeric guard** — unlike the sibling `AgentCostSensor`, which checks `isinstance(cost, (int, float))`. A bridge returning `totalIn: null` (or a non-numeric string) makes the property raise. Two lesser issues in the same code: it returns `0` (not `None`) when `totals` is present but empty, and both new sensors set a `_attr_translation_key` with no matching `strings.json` entry (the `name` property wins, so the key is dead).

**Verify:** `AgentTokensSensor.native_value` returns `None` (never raises) for `{"totals": {"totalIn": null, "totalOut": 5}}` and for `{"totals": {}}`, and returns `8` for `{"totals": {"totalIn": 5, "totalOut": 3}}`.

## Affected Area

- **Component:** `sensor.py` (`AgentTokensSensor`, `AgentCostSensor`)
- **Origin:** CR-0009

## Environment

- **Version:** 0.10.0

---

## Reproduction Steps

1. Bridge `GET /v1/agents/{id}/usage` returns `{"totals": {"totalIn": null, "totalOut": 5}}` (a common "unpopulated field = null" shape).
2. HA reads `AgentTokensSensor.native_value`.

## Expected Behaviour

`None` (state unknown) — no exception.

## Actual Behaviour

`int(None)` raises `TypeError` inside the property → HA logs an error and the entity state goes unavailable. A non-numeric string would raise `ValueError`.

---

## Root Cause Analysis

The token sensor coerces with bare `int(...)`; the cost sensor (right below) already guards with `isinstance`. The two were written inconsistently.

## Fix Description

Fixed in `fix/code-review-0.10.1` (shipped as 0.10.1). See Files Modified below.

Sum only numeric `totalIn`/`totalOut` values; return `None` when neither is numeric (fixes the crash and the 0-vs-None nuance). Remove the dead `_attr_translation_key` from both new sensors (the `name` property supplies the name, matching `MessageReceivedEvent`).

### Files Modified

| File | Change |
|------|--------|
| `sensor.py` | Numeric-guard `AgentTokensSensor.native_value`; drop dead `_attr_translation_key` |

### Tests Added

| Test | Description | File |
|------|-------------|------|
| TC-bg0006 | token native_value: None on null/empty totals, sum on numeric; cost None on null | `tests/test_sensor.py` |

---

## Verification

- [x] Fix verified in development (unit tests added)
- [x] Regression tests pass (CI green)

**Verified by:** unit tests + CI
**Verification date:** 2026-06-09
**Verification depth:** functional

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-06-09 | Claude | Bug reported (RV0006 xhigh code review of 0.10.0) |
