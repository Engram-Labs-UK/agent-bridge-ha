<!--
Template: Bug Report (Streamlined)
File: sdlc-studio/bugs/BG{NNNN}-{slug}.md
Status values: See reference-outputs.md
Related: help/bug.md, reference-bug.md
-->
# BG0008: Coordinator emits usage/doctor by reference (aliasing hazard)

> **Status:** Fixed
> **Severity:** Low
> **Priority:** P3
> **Reporter:** Claude (RV0006 code review)
> **Assignee:** —
> **Created:** 2026-06-09
> **Verification depth:** functional

## Summary

`_async_update_data` emits `usage=self._usage` and `doctor=self._doctor` into `CoordinatorData`, and `sensor._usage()` returns a live reference into `coordinator.data`. A consumer that mutates the returned mapping would corrupt the coordinator's internal observability state. Latent (no current mutator), but a real aliasing hazard.

**Verify:** `coordinator.data["usage"]` is not the same object as `coordinator._usage` (a fresh top-level mapping is emitted each poll).

## Affected Area

- **Component:** `coordinator.py` (emit), `sensor.py` (`_usage()`)
- **Origin:** CR-0009

## Environment

- **Version:** 0.10.0

---

## Reproduction Steps

1. A listener/helper does `coordinator.data["usage"]["cora"] = {...}` (or mutates the dict `_usage()` returns).
2. The coordinator's `self._usage` is mutated in place; the corruption survives until the next discovery rebuild.

## Expected Behaviour

The emitted `CoordinatorData` should not hand out the coordinator's working mappings by reference.

## Actual Behaviour

`usage`/`doctor` are the coordinator's own dicts.

---

## Fix Description

Fixed in `fix/code-review-0.10.1` (shipped as 0.10.1). See Files Modified below.

Emit a shallow copy (`dict(self._usage)` / `dict(self._doctor)`) at every emit site (success + hard-error path). Document that the nested per-agent payloads are read-only by consumer contract (deep copy each poll would be wasteful for a P3).

### Files Modified

| File | Change |
|------|--------|
| `coordinator.py` | emit `dict(self._usage)` / `dict(self._doctor)` |

### Tests Added

| Test | Description | File |
|------|-------------|------|
| TC-bg0008 | `data["usage"] is not coordinator._usage` | `tests/test_coordinator.py` |

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
