# BG0001: No way to change voice agent after initial setup

> **Status:** Open
> **Severity:** High
> **Priority:** P1
> **Reporter:** Darren
> **Assignee:** --
> **Created:** 2026-04-06

## Summary

After the initial config flow, there is no way to change which bridge agent handles voice requests. The options flow (`Settings > Devices & Services > Agent Bridge > Configure`) exposes context settings, tool calls, SSL, and debug logging -- but not the `default_agent` or `voice_agent` selection. The only way to change the agent is to delete and re-add the integration.

## Affected Area

- **Epic:** [EP0001: Bridge Foundation](../epics/EP0001-bridge-foundation.md)
- **Story:** [US0004: Config Flow](../stories/US0004-config-flow.md)
- **Component:** config_flow.py (AgentBridgeOptionsFlow)

## Environment

- **Version:** 0.1.0
- **Platform:** HA 2026.4.1 (HAOS, amd64)

---

## Reproduction Steps

1. Set up Agent Bridge integration with `cora` as voice agent
2. Go to Settings > Devices & Services > Agent Bridge > Configure
3. Look for a way to change the voice agent to a different bridge agent
4. No agent selection field exists in the options form

## Expected Behaviour

The options flow should include `default_agent` and `voice_agent` dropdowns populated from the bridge's discovery endpoint, allowing the user to switch agents without re-adding the integration.

## Actual Behaviour

Options flow only shows: context_max_chars, context_strategy, enable_per_agent_entities, enable_tool_calls, thinking_timeout, ssl_verify, debug_logging. No agent selection fields.

---

## Root Cause Analysis

The `AgentBridgeOptionsFlow.async_step_init()` in `config_flow.py` only exposes the secondary options. The agent selection fields (`default_agent`, `voice_agent`) are in `entry.data` (set during initial config flow step 2) and are never presented in the options flow.

Adding them to the options flow requires calling `client.discover()` to get the current agent list, then showing a dropdown -- the same pattern as the initial setup's `async_step_agents`.

## Fix Description

> *Pending*

Add `default_agent` and `voice_agent` selectors to the options flow. Requires:
1. Create bridge client from config entry data in options flow
2. Call `client.discover()` to get current agents
3. Show agent dropdown fields pre-populated with current selection
4. On save, update `entry.data` via `hass.config_entries.async_update_entry()`

### Files Modified

| File | Change |
|------|--------|
| `config_flow.py` | Add agent selection to `AgentBridgeOptionsFlow.async_step_init()` |

---

## Verification

- [ ] Fix verified in development
- [ ] Regression tests pass
- [ ] No side effects observed

**Verified by:** --
**Verification date:** --

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-04-06 | Darren | Bug reported from live deployment |
