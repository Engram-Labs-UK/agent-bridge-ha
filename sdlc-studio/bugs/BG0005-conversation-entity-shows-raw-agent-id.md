<!--
Template: Bug Report (Streamlined)
File: sdlc-studio/bugs/BG{NNNN}-{slug}.md
Status values: See reference-outputs.md
Related: help/bug.md, reference-bug.md
-->
# BG0005: Conversation entity shows the raw bridge agent id instead of the agent name

> **Status:** Fixed
> **Severity:** Medium
> **Priority:** P2
> **Reporter:** Darren Benson
> **Assignee:** —
> **Created:** 2026-06-09
> **Verification depth:** functional

## Summary

In the Assist "Conversation agent" picker the agent appears as **"Cora openclaw-openclaw-cora"** - the raw bridge agent id leaks into the user-facing name. It should read like the options-flow picker (**"Cora (deskpoint)"**, i.e. `name (crew)`), consistent across every surface.

**Verify:** `conversation entity friendly_name == agent name (+ crew), never the raw agent id` - on the live install, `conversation.openclaw_openclaw_cora_openclaw_openclaw_cora` must not contain the substring `openclaw-openclaw-cora`.

## Affected Area

- **Epic:** EP0007 (bridge v4.36 + modern HA realignment) - one conversation entity per agent (US0025)
- **Story:** US0025 (per-agent ConversationEntity); naming relates to CR-0003 / [CR-0007](../change-requests/cr0007.md)
- **Component:** `conversation.py`

## Environment

- **Version:** integration 0.9.0, HA 2026.5.x, bridge v4.36 (live: HA `10.0.0.209`, bridge `10.0.0.210:18780`)
- **Platform:** Home Assistant Assist (conversation-agent selector)

---

## Reproduction Steps

1. Configure Agent Bridge and select an agent in the options "Agent" picker (writes `default_agent`) **without** adding it via "Add agent" (no conversation subentry).
2. Open Settings → Voice assistants → an assistant → Conversation agent dropdown.
3. Observe the agent listed as "Cora openclaw-openclaw-cora".

## Expected Behaviour

The conversation entity is named from the agent's discovered friendly name (and crew), matching the options picker: **"Cora (deskpoint)"**. No raw id on screen.

## Actual Behaviour

The friendly name is **"Cora openclaw-openclaw-cora"** = `device name` ("Cora") + `entity name` (the raw agent id). The entity id is frozen as `conversation.openclaw_openclaw_cora_openclaw_openclaw_cora` (the id appears twice), proving both device and entity were created with the raw id as the name.

Live confirmation (`GET /api/states`):

```
conversation.openclaw_openclaw_cora_openclaw_openclaw_cora -> 'Cora openclaw-openclaw-cora'
conversation.dbee_dbee                                      -> 'dbee'   (clean: device==entity name)
```

---

## Root Cause Analysis

`conversation.py:_agents_from_entry` legacy fallback (lines 571-574) reuses the raw agent **id** as the display name when no conversation subentry exists:

```python
if not agents:
    default_agent = entry.data.get(CONF_DEFAULT_AGENT)   # this is the agent id
    if default_agent:
        agents.append((default_agent, default_agent, None, DEFAULT_PROMPT))
        #              agent_id       agent_name  ← id reused as name
```

`AgentBridgeConversationEntity.__init__` then sets `_attr_name = agent_name` and `DeviceInfo(name=agent_name)` (lines 657, 662), so both device and entity carry the id. (The "Cora" prefix now seen is a later device-level rename; the entity name is still the id.)

Two defects:
1. **Fallback path** does not resolve the friendly name from discovery (`agents_by_id` is available in `async_setup_entry` but not passed to `_agents_from_entry`).
2. **Naming is inconsistent across surfaces:** options picker uses `_agent_label` (`name (crew)`); the subentry path uses `chosen["name"]` (`name`); the fallback uses the id.

## Fix Description

Fixed in Wave 1 (`chore/code-health-wave1`). The picker formatter `_agent_label` was lifted into `helpers.agent_label` as the single shared name formatter (`name (crew)`, else the bare name, never the raw id). `conversation.async_setup_entry` and `ai_task.async_setup_entry` now resolve the display name from discovery (`agents_by_id`) via `agent_label`, falling back to the subentry title / id only when the bridge has no record. To make `name (crew)` available to the entities, the coordinator now discovers with `include=["crew"]` and parses the crew via `agent_crew` into `AgentInfo.crew` (previously never populated).

### Files Modified

| File | Change |
|------|--------|
| `helpers.py` | New shared `agent_label`; simplified to drop the ugly `(status)`/`(unknown)` fallback |
| `config_flow.py` | Use shared `agent_label` (removed the local duplicate) |
| `conversation.py` | Resolve entity/device name via `agent_label` from discovery |
| `ai_task.py` | Same display-name resolution |
| `coordinator.py` | `discover(include=["crew"])` + `crew=agent_crew(raw)` so crew is populated |

### Tests Added

| Test | Description | File |
|------|-------------|------|
| TestAgentLabel | `name (crew)` / bare name / crew-dict shape / never the raw id when named | `tests/test_helpers.py` |

---

## Verification

- [x] Fix verified in development (unit: `TestAgentLabel`; ruff + format clean; pytest green in CI)
- [x] Regression tests pass (CI)
- [ ] Live: `conversation.*` friendly name shows `name (crew)`, no raw id -- confirm after a live HA reload (entity_id stays frozen; only friendly_name updates)

**Verified by:** CI (functional); live friendly_name check pending a reload of the live install
**Verification date:** 2026-06-09
**Verification depth:** functional

> A bug cannot be marked **Fixed** until depth is at least `functional`.

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-06-09 | Darren Benson | Bug reported; root cause confirmed from live `/api/states` |
