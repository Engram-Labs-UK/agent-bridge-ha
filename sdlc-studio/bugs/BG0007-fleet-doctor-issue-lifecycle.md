<!--
Template: Bug Report (Streamlined)
File: sdlc-studio/bugs/BG{NNNN}-{slug}.md
Status values: See reference-outputs.md
Related: help/bug.md, reference-bug.md
-->
# BG0007: Fleet-doctor repair issue wrongly cleared on bridge outage + churns every poll

> **Status:** Fixed
> **Severity:** Medium
> **Priority:** P2
> **Reporter:** Claude (RV0006 code review)
> **Assignee:** —
> **Created:** 2026-06-09
> **Verification depth:** functional

## Summary

The `fleet_doctor` repair issue (CR-0009) has a fragile lifecycle. (1) The coordinator **hard-error** `CoordinatorData` omits the `doctor` key, so `async_check_doctor_verdict` reads `{}` and **deletes** the repair issue whenever the bridge is unreachable — even if the fleet is genuinely CRITICAL. (2) The check is a coordinator listener firing every ~30s poll, but the doctor verdict only refreshes every ~300s, so it calls `ir.async_create_issue`/`async_delete_issue` redundantly on every poll.

**Verify:** the hard-error `CoordinatorData` carries `usage`/`doctor` forward (so the issue is not cleared by an outage), and `async_check_doctor_verdict` only writes to the issue registry when the applied verdict state changes.

## Affected Area

- **Component:** `coordinator.py` (error path + emit), `drift.py` (`async_check_doctor_verdict`)
- **Origin:** CR-0009

## Environment

- **Version:** 0.10.0

---

## Reproduction Steps

1. Doctor reports `CRITICAL` → `fleet_doctor` repair raised.
2. Bridge becomes unreachable (>3 consecutive poll failures).
3. The hard-error `CoordinatorData` has no `doctor` key → listener reads `{}` → verdict `""` → repair issue deleted.

## Expected Behaviour

A bridge outage is signalled by `connected=False`/`bridge_status="error"`; the last-known doctor verdict (and its repair issue) should persist, not be cleared by connectivity loss.

## Actual Behaviour

The `fleet_doctor` repair issue disappears during the outage and only reappears on the next successful discovery (≤300s after recovery).

---

## Root Cause Analysis

The hard-error return omits `usage`/`doctor` (they are `NotRequired`), unlike the cached-data path which spreads `_last_good_data`. Separately, the listener is unconditional per poll.

## Fix Description

Fixed in `fix/code-review-0.10.1` (shipped as 0.10.1). See Files Modified below.

Add `usage=self._usage`/`doctor=self._doctor` to the hard-error `CoordinatorData` (carry-forward). Gate `async_check_doctor_verdict` so it only touches the issue registry when the applied state (WARNING/CRITICAL/none) changes from the last applied state (with a first-call sentinel so a stale issue from a prior session is reconciled once).

### Files Modified

| File | Change |
|------|--------|
| `coordinator.py` | hard-error path carries `usage`/`doctor` |
| `drift.py` | gate registry writes on applied-state change |

### Tests Added

| Test | Description | File |
|------|-------------|------|
| TC-bg0007a | hard-error `CoordinatorData` includes carried `usage`/`doctor` | `tests/test_coordinator.py` |
| TC-bg0007b | verdict-change gate: no redundant registry write when unchanged | `tests/test_drift_surface.py` |

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
