# BG0002: Config flow asks for two agents when only voice agent is needed

> **Status:** Fixed
> **Severity:** Medium
> **Priority:** P2
> **Reporter:** Darren
> **Assignee:** --
> **Created:** 2026-04-06

## Summary

The initial config flow step 2 asks the user to select both a "Default Chat Agent" and a "Voice Agent". Since HA only supports one conversation agent per integration (no per-agent entities possible due to HA API limitations), and the primary use case is voice, the two-agent selection is confusing. The `default_agent` field serves no practical purpose when the integration is used exclusively through voice pipelines.

## Affected Area

- **Epic:** [EP0001: Bridge Foundation](../epics/EP0001-bridge-foundation.md)
- **Story:** [US0004: Config Flow](../stories/US0004-config-flow.md)
- **Component:** config_flow.py (async_step_agents)

## Environment

- **Version:** 0.1.0
- **Platform:** HA 2026.4.1 (HAOS, amd64)

---

## Reproduction Steps

1. Add the Agent Bridge integration
2. Enter bridge URL and token (step 1 passes)
3. Step 2 shows two dropdowns: "Default Chat Agent" and "Voice Agent"
4. User is confused about the difference and why two are needed

## Expected Behaviour

Config flow should ask for a single agent selection ("Agent") since the integration registers one conversation agent. The voice/text distinction should be handled via the options flow if needed at all, not forced during initial setup.

## Actual Behaviour

Step 2 presents two mandatory-looking agent selectors. The `default_agent` is used for text input (automations, developer tools) and `voice_agent` for voice pipelines, but this distinction is not explained in the UI and adds unnecessary complexity to first-time setup.

---

## Root Cause Analysis

The PRD originally specified separate default and voice agents (PRD Section 3, "Primary Conversation Agent" AC). This made sense when per-agent conversation entities were planned (assign different agents to different pipelines). Since HA's API only allows one conversation agent per integration, having two agent fields in the config creates a confusing UX with minimal benefit.

## Suggested Fix

**Option A (minimal):** Make `voice_agent` optional in step 2 with a note "Defaults to the selected agent". Reduce to a single required field.

**Option B (simplify):** Remove `voice_agent` from the config flow entirely. Use a single "Agent" field. Add voice_agent as an optional override in the options flow for power users who want text and voice to route differently.

### Files Modified

| File | Change |
|------|--------|
| `config_flow.py` | Simplify `async_step_agents` to single agent selector |
| `strings.json` | Update step 2 field labels |
| `translations/en.json` | Update step 2 field labels |

---

## Fix Outcome

Resolved by the EP0007 realignment (Option B). Initial setup (`async_step_agents`)
now asks for a **single** `CONF_DEFAULT_AGENT`, and both `default_agent` and
`voice_agent` are set to that one choice (`config_flow.py:133-154`). Multiple agents
are now added as separate conversation entities via the "Add agent" subentry flow
(CR-0003/US0025), which superseded the original two-field design. Closed in Wave 5;
code already in `main`.

## Verification

- [x] Fix verified in development (setup shows one agent selector; `test_config_flow` covers entry creation)
- [x] Regression tests pass (CI)
- [x] No side effects observed

**Verified by:** code review + CI
**Verification date:** 2026-06-09

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-04-06 | Darren | Bug reported from live deployment UX feedback |
