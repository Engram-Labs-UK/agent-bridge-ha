# US0025: Migrate to `ConversationEntity` + config subentries

> **Status:** Done
> **Epic:** [EP0007: Bridge v4.36 + Modern HA Re-Alignment](../epics/EP0007-bridge-v436-modern-ha-realignment.md)
> **Owner:** Darren Benson
> **Created:** 2026-06-01

## User Story

**As a** Home Assistant operator
**I want** one `ConversationEntity` per bridge agent created via config subentries
**So that** per-agent conversation works on the modern HA model and dead legacy registration is removed

## User Story Context

G2: root cause of the per-agent breakage. The component subclasses the legacy `AbstractConversationAgent` and registers via `async_set_agent(hass, entry, agent, agent_id=...)` — a kwarg HA never accepted; the call site was removed so `async_setup_per_agent_conversations` is now uncalled dead code, yet US0015 is marked Done. This replaces that with the modern entity-platform + config-subentry model HA's OpenAI/Google integrations use (HA 2025.2+), superseding CR-0001's one-entry-per-agent workaround.

## Acceptance Criteria

### AC1: One `ConversationEntity` per agent via subentries
- **Given** the integration
- **When** set up
- **Then** a `conversation` platform creates one `AgentBridgeConversationEntity` per configured bridge agent via `async_add_entities` under config subentries, each appearing in the Assist picker
- **Verify:** `pytest` that setting up an entry with N agents registers N `ConversationEntity` instances

### AC2: Platform + manifest dependency registered
- **Given** `const.py`
- **Then** `PLATFORMS` includes `'conversation'` and `manifest` dependencies includes `'conversation'`
- **Verify:** `grep -q "conversation" custom_components/*/const.py` and the manifest `dependencies`

### AC3: Legacy registration deleted
- **Given** the codebase
- **Then** `async_set_agent`/`async_unset_agent` and `async_setup_per_agent_conversations` are deleted (no callers remain)
- **Verify:** `grep` asserting `async_set_agent` is absent from `custom_components/`

## Scope

### In Scope
- A `conversation` entity platform with one entity per agent via config subentries
- `PLATFORMS` + manifest `dependencies` updates
- Deletion of the dead `async_set_agent`/`async_unset_agent`/`async_setup_per_agent_conversations` code

### Out of Scope
- `_async_handle_message`/`ChatLog` adoption (US0026)
- Actuation (US0027)
- Forced entity-ID migration for existing single-entry installs (offer, do not force)

## Technical Notes

- Mirrors the OpenAI/Google conversation integrations' subentry pattern (HA 2025.2+).
- Supersedes CR-0001's one-entry-per-agent workaround.
- Config-subentry migration may cause entity-ID churn for existing single-entry installs — offer migration, do not force it.

## Dependencies

### Story Dependencies

| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| US0021 | Decision | Actuation strategy decided (gates entity/tool wiring shape) | Proposed |

## Estimation

**Story Points:** 8
**Complexity:** High

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-06-01 | Claude | Initial story for EP0007 (CR-0002 redesign) |
| 2026-06-02 | Claude | R2 implemented + unit-tested on HA 2026.2.3 (pytest green); status -> Done |
