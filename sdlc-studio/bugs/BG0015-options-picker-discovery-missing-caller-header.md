<!--
Template: Bug Report (Streamlined)
File: sdlc-studio/bugs/BG{NNNN}-{slug}.md
Status values: See reference-outputs.md
Related: help/bug.md, reference-bug.md
-->
# BG0015: Options-flow agent discovery omits the `x-bridge-mcp-caller` header — picker silently degrades on a caller-enforcing bridge

> **Status:** Fixed
> **Severity:** Low
> **Priority:** P3
> **Reporter:** Code + security review (RV-requested, 2026-07-04)
> **Assignee:** —
> **Created:** 2026-07-04
> **Verification depth:** functional

## Summary

BG0004 established that the v4.36+ bridge can reject calls whose caller identity is not a registered agent, and the fix routes every client through `resolve_caller_id(entry)`. The subentry flow's `_discover_agents` (config_flow.py:75-90) passes `caller_id=resolve_caller_id(entry)` accordingly — but the options flow's `_get_agent_options` (config_flow.py:418-437) builds its own `BridgeClient` **without** `caller_id`. Against a bridge that enforces caller identity on `/v1/discovery`, the options picker's discovery 403s, is swallowed by the broad `except Exception`, and the dropdown silently degrades to just the currently configured agent — a BG0004-family regression hiding as "the picker only shows one agent".

**Verify:** `_get_agent_options` constructs its `BridgeClient` with `caller_id=resolve_caller_id(self._config_entry)` (parity with `_discover_agents`), and a test asserts the header is sent from the options flow's discovery call.

## Affected Area

- **Component:** `config_flow.py` (`AgentBridgeOptionsFlow._get_agent_options`)
- **Origin:** BG0004 fix applied unevenly across the three discovery call sites

## Environment

- **Version:** 0.11.0; only manifests when the bridge enforces caller identity on discovery

---

## Reproduction Steps

1. Configure the bridge to require a registered caller on `/v1/discovery`.
2. Open the integration's options form.

## Expected Behaviour

The agent dropdown lists all selectable agents (`name (crew)`), same as the subentry picker.

## Actual Behaviour

Discovery 403s; the fallback returns `{current: current}` and the picker shows only the already-selected agent id.

---

## Root Cause Analysis

`_get_agent_options` predates the shared `_discover_agents` helper and was never converged onto it.

## Fix Description

`_get_agent_options` now delegates discovery to the shared `_discover_agents(self.hass, self._config_entry)` helper (which passes `caller_id=resolve_caller_id(entry)`, ssl-verify option and `include=crew`), keeping only the selectable-filter + label logic locally. The three discovery call sites now share one client construction path (first-run setup remains header-less by design — no entry exists yet).

### Files Modified

| File | Change |
|------|--------|
| `config_flow.py` | `_get_agent_options` delegates to `_discover_agents` |
| `tests/test_config_flow.py` | asserts the options-flow discovery client is built with `caller_id` = default agent |

---

## Verification

- [x] Fix verified in development (unit) — TDD: red first, green after; suite 336 passed

**Verified by:** unit test (`tests/test_config_flow.py::TestOptionsFlow::test_agent_options_discovery_sends_caller_id`)
**Verification date:** 2026-07-04
**Verification depth:** functional

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-07-04 | Code + security review | Found comparing the three discovery call sites for BG0004 parity |
