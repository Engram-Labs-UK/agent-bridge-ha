# US0009: Session Persistence

> **Status:** Done
> **Epic:** [EP0002: Conversation & Home Control](../epics/EP0002-conversation-and-control.md)
> **Owner:** Darren Benson
> **Created:** 2026-04-05

## User Story

**As the** integration
**I want** agent-scoped session IDs that persist across HA restarts
**So that** agents maintain conversation context through the bridge's channel system

## Context

The bridge uses channels for multi-turn conversation persistence. This story creates a session manager (in `__init__.py`, not a separate file) that generates one session per agent, persists them to HA Store, and loads them on startup. Sessions are sent as the `channel` field in chat requests. Format: `agent:{agent_id}:assist_{random_hex}`. One session per agent (not per HA conversation_id) -- the bridge owns conversation history, and agent-scoped sessions keep context coherent across voice and text inputs to the same agent.

---

## Acceptance Criteria

### AC1: Session ID format
- **Given** an agent_id
- **When** a new session is created
- **Then** the session ID follows the format `agent:{agent_id}:assist_{random_hex}` where random_hex is a sufficiently unique hex string

### AC2: One session per agent
- **Given** an agent_id that already has a session
- **When** a conversation request arrives for that agent
- **Then** the existing session is reused, not a new one created

### AC3: Persistence to HA Store
- **Given** sessions exist in memory
- **When** sessions are created or the integration saves state
- **Then** sessions are written to `.storage/agent_bridge.sessions` via HA Store

### AC4: Load on startup
- **Given** `.storage/agent_bridge.sessions` contains saved sessions
- **When** the integration starts (async_setup_entry)
- **Then** sessions are loaded from store and available immediately

### AC5: Channel field in chat request
- **Given** a conversation request for an agent
- **When** the chat request is sent to the bridge
- **Then** the session ID is included as the `channel` field in the request body

### AC6: New agent gets new session
- **Given** a conversation request for an agent_id with no existing session
- **When** the session manager is queried
- **Then** a new session ID is generated, stored, and persisted

### AC7: Unload does not delete sessions
- **Given** a loaded integration with active sessions
- **When** async_unload_entry is called
- **Then** sessions remain in HA Store for next startup (not cleared)

---

## Scope

### In Scope
- Session manager logic in `custom_components/agent_bridge/__init__.py`
- HA Store integration for `.storage/agent_bridge.sessions`
- Session creation, lookup, and persistence
- Loading sessions on integration startup

### Out of Scope
- Session cleanup/rotation (future enhancement)
- Per-conversation_id sessions (explicitly rejected -- one per agent)
- Bridge channel management (bridge owns channel lifecycle)

---

## Technical Notes

Use `homeassistant.helpers.storage.Store` with version 1 and key `agent_bridge.sessions`. The store data shape is a dict mapping agent_id to session_id string. Generate random hex via `secrets.token_hex(8)` (16 hex chars). The session manager can be a simple class or a pair of functions stored on `hass.data[DOMAIN][entry.entry_id]`. Load is async (`await store.async_load()`), save is async (`await store.async_save(data)`). Save after each new session creation.

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| Store file does not exist (first run) | Create empty session dict, generate sessions on demand |
| Store file is corrupted / invalid JSON | Log warning, start with empty session dict |
| Agent removed from bridge but session exists | Session remains in store (harmless); no cleanup needed |
| Multiple config entries (unlikely but possible) | Each config entry has its own store key or namespace |
| HA restart mid-save | HA Store handles atomic writes; no data loss |
| Concurrent session lookups for same agent | First call creates, second call reuses (no race condition with single-threaded async) |

---

## Test Scenarios

- [ ] New agent generates session in correct format: `agent:{id}:assist_{hex}`
- [ ] Same agent returns same session on second lookup
- [ ] Different agents get different sessions
- [ ] Sessions saved to HA Store after creation
- [ ] Sessions loaded from HA Store on startup
- [ ] Session ID sent as channel field in chat request
- [ ] Missing store file: starts with empty dict, no error
- [ ] Corrupted store file: logs warning, starts with empty dict
- [ ] Unload does not delete stored sessions
- [ ] Session hex component is 16 characters (token_hex(8))

---

## Dependencies

### Story Dependencies

| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| [US0005](US0005-coordinator-and-setup.md) | Hard | __init__.py setup/teardown lifecycle, hass.data structure | Done |

### External Dependencies

| Dependency | Type | Status |
|------------|------|--------|
| Home Assistant Core 2025.1.0+ | Framework | Available |
| HA Store (homeassistant.helpers.storage) | Internal API | Available |

---

## Estimation

**Story Points:** 2
**Complexity:** Low

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-04-05 | Claude | Initial story generation |
