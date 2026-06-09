<!--
Template: Bug Report (Streamlined)
File: sdlc-studio/bugs/BG{NNNN}-{slug}.md
Status values: See reference-outputs.md
Related: help/bug.md, reference-bug.md
-->
# BG0011: Fleet-doctor repair issue is too noisy — raises a persistent warning for a benign idle fleet

> **Status:** Fixed
> **Severity:** Medium
> **Priority:** P2
> **Reporter:** Darren Benson
> **Assignee:** —
> **Created:** 2026-06-09
> **Verification depth:** functional

## Summary

The CR-0009 `fleet_doctor` repair issue raised an HA repair notification for a bridge doctor **WARNING** verdict: *"fleet: no fleet activity for ~46 min (whole fleet quiet)"*. An idle/quiet fleet is normal for a home install and is not actionable, so surfacing it as a persistent HA repair is noise. HA repair issues should be reserved for actionable problems.

**Verify:** a WARNING doctor verdict does **not** raise an HA repair issue (it stays in the diagnostics download); only CRITICAL raises one (severity ERROR).

## Affected Area

- **Component:** `drift.py` (`_VERDICT_SEVERITY`, `async_check_doctor_verdict`)
- **Origin:** CR-0009

## Environment

- **Version:** 0.10.2 (fix ships in 0.10.3); live HA 2026.6.1, bridge v4.141

---

## Reproduction Steps

1. Leave the fleet idle for a while.
2. The bridge doctor returns `verdict: WARNING`, finding *"no fleet activity… whole fleet quiet"*.
3. HA shows a persistent repair: "The bridge doctor reports a WARNING verdict: fleet: no fleet activity…".

## Expected Behaviour

A quiet fleet (advisory WARNING) does not nag via a repair notification. The full verdict remains available in the integration's diagnostics download for anyone who wants it.

## Actual Behaviour

Every doctor WARNING (including benign idle states) raised a persistent HA repair.

---

## Root Cause Analysis

`_VERDICT_SEVERITY` mapped WARNING → `IssueSeverity.WARNING`, so any WARNING verdict raised a repair. Per-agent degradation is already surfaced by the health sensors/binary_sensor, so WARNING-as-repair is redundant and, for idle states, false noise.

## Fix Description

Only `CRITICAL` verdicts raise a repair issue (the home's agents genuinely can't function). WARNING-level findings are advisory and remain in the diagnostics download + the `doctor` coordinator data, not a repair. The verdict-change gate (BG0007) clears any existing WARNING repair on the next poll.

### Files Modified

| File | Change |
|------|--------|
| `drift.py` | `_VERDICT_SEVERITY` keeps only CRITICAL → ERROR |
| `tests/test_drift_surface.py` | WARNING asserts no repair issue; CRITICAL still raises |

---

## Verification

- [x] Fix verified in development (unit)
- [ ] Live: the WARNING repair auto-clears after the 0.10.3 update + restart

**Verified by:** unit tests + CI; live clear pending update
**Verification date:** 2026-06-09
**Verification depth:** functional

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-06-09 | Darren Benson | Reported on the live install (benign "fleet quiet" WARNING raised a repair) |
