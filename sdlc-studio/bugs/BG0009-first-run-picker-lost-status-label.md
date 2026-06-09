<!--
Template: Bug Report (Streamlined)
File: sdlc-studio/bugs/BG{NNNN}-{slug}.md
Status values: See reference-outputs.md
Related: help/bug.md, reference-bug.md
-->
# BG0009: First-run agent picker lost its health/crew label (BG0005 regression)

> **Status:** Fixed
> **Severity:** Low
> **Priority:** P3
> **Reporter:** Claude (RV0006 code review)
> **Assignee:** —
> **Created:** 2026-06-09
> **Verification depth:** functional

## Summary

BG0005 merged the picker's `_agent_label` into the shared `helpers.agent_label`, dropping its old `name (status)` fallback. The initial-setup picker (`config_flow.async_step_user` → bare `discover()`, no `include=crew`) now shows bare agent names with no parenthetical, where it used to show `name (status)`. The options + subentry pickers are unaffected (they use `include=crew` → `name (crew)`). Best fixed at altitude: make the remaining `discover()` calls request crew too, so every picker is consistent.

**Verify:** `config_flow.async_step_user` and `AgentBridgeOptionsFlow._get_agent_options` call `client.discover(include=["crew"])`, so the first-run picker renders `name (crew)`.

## Affected Area

- **Component:** `config_flow.py` (`async_step_user`, `_get_agent_options`)
- **Origin:** BG0005 (shared `agent_label`)

## Environment

- **Version:** 0.10.0

---

## Reproduction Steps

1. Add the integration (first run); reach the agent-selection step.
2. The dropdown shows `Cora` instead of `Cora (deskpoint)` / the old `Cora (healthy)`.

## Expected Behaviour

The picker shows `name (crew)`, consistent with the options and "Add agent" pickers.

## Actual Behaviour

Bare `name` (the health/crew hint is gone) on first-run setup.

---

## Fix Description

Fixed in `fix/code-review-0.10.1` (shipped as 0.10.1). See Files Modified below.

Pass `include=["crew"]` to the two remaining `discover()` calls (`async_step_user`, `_get_agent_options`). No label special-case; `agent_label` stays clean (`name (crew)` / `name`). An older bridge without crew falls back to bare `name` as today.

### Files Modified

| File | Change |
|------|--------|
| `config_flow.py` | `discover(include=["crew"])` in `async_step_user` + `_get_agent_options` |

### Tests Added

| Test | Description | File |
|------|-------------|------|
| TC-bg0009 | both flows call `discover` with `include=["crew"]` | `tests/test_config_flow.py` |

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
