# US0006: Entity Exposure

> **Status:** Done
> **Epic:** [EP0002: Conversation & Home Control](../epics/EP0002-conversation-and-control.md)
> **Owner:** Darren Benson
> **Created:** 2026-04-05

## User Story

**As the** conversation agent
**I want** HA entity state formatted as AI-consumable context
**So that** bridge agents understand the home and can target devices by entity_id

## Context

Entity exposure builds a text block describing exposed HA entities -- their IDs, names, states, areas, and relevant attributes. This is injected into the system prompt so agents know what devices exist and their current state. Built fresh per conversation request (never cached) to reflect current state. Adapted from the OpenClaw fork's proven exposure patterns (ADR-004).

---

## Acceptance Criteria

### AC1: Entity formatting
- **Given** an exposed HA entity with state, friendly name, and area
- **When** the exposure builder runs
- **Then** each entity is formatted with entity_id, friendly_name, state, area (if assigned), and domain-relevant attributes

### AC2: Voice assistant expose settings
- **Given** HA's voice assistant entity expose settings
- **When** the exposure builder collects entities
- **Then** only entities marked as exposed via `async_should_expose()` are included

### AC3: 250-entity cap
- **Given** more than 250 exposed entities
- **When** the exposure builder runs
- **Then** at most MAX_ENTITIES (250) entities are included in the output

### AC4: Truncation strategy
- **Given** the entity context exceeds context_max_chars
- **When** context_strategy is "truncate"
- **Then** the context is truncated to fit within the character limit with a note indicating truncation

### AC5: Clear strategy
- **Given** the entity context exceeds context_max_chars
- **When** context_strategy is "clear"
- **Then** entity context is omitted entirely with a note explaining why

### AC6: Template entities and groups
- **Given** template sensors, template binary sensors, and group entities that are exposed
- **When** the exposure builder runs
- **Then** they are included as-is with no type-based filtering (per TRD Q2 decision)

### AC7: Fresh per request
- **Given** entity state changes between conversation requests
- **When** a new conversation request arrives
- **Then** the exposure builder reads current state from HA registries, not cached data

### AC8: Area resolution
- **Given** an entity assigned to a device in an area
- **When** the exposure builder formats the entity
- **Then** the area name is resolved via device registry and area registry and included in the output

### AC9: Domain-relevant attributes
- **Given** entities of different domains (light, climate, media_player, cover, etc.)
- **When** the exposure builder formats attributes
- **Then** only domain-relevant attributes are included (e.g. brightness/colour for lights, temperature/hvac_mode for climate), not the full attribute dict

---

## Scope

### In Scope
- `custom_components/agent_bridge/exposure.py`
- Entity collection from HA state machine filtered by expose settings
- Entity formatting (entity_id, friendly_name, state, area, attributes)
- 250-entity cap enforcement
- Truncation and clear overflow strategies driven by config
- Area resolution via device and area registries

### Out of Scope
- System prompt assembly (US0007)
- Tool call entity validation (US0008 -- uses exposure list but validation is in tool_executor)
- Per-agent entity filtering (EP0004)

---

## Technical Notes

Use `async_should_expose()` from `homeassistant.components.conversation` (or the appropriate HA voice expose helper) to check which entities are exposed. Access entity states via `hass.states.async_all()`, device registry via `dr.async_get(hass)`, area registry via `ar.async_get(hass)`. The function should return both the formatted text block and the set of exposed entity_ids (the latter is used by the tool executor for validation). Config values `context_max_chars` and `context_strategy` come from the config entry options.

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| Zero exposed entities | Return empty context with note: "No entities are exposed to voice assistants" |
| Entity has no area assignment | Omit area field for that entity, include everything else |
| Entity has no friendly_name | Fall back to entity_id as the display name |
| Entity state is "unavailable" or "unknown" | Include the entity with its current state (agents should know) |
| context_max_chars set to minimum (1000) | Truncation/clear triggers earlier; cap still respected |
| Device exists but area deleted | Omit area for affected entities |
| Large attribute values (e.g. long media title) | Truncate individual attribute values to a reasonable length |

---

## Test Scenarios

- [ ] Exposed entity appears in output with entity_id, friendly_name, state
- [ ] Non-exposed entity is excluded from output
- [ ] Entity with area shows area name in output
- [ ] Entity without area omits area field
- [ ] Output capped at 250 entities when more are exposed
- [ ] Truncation strategy: output fits within context_max_chars with truncation note
- [ ] Clear strategy: output replaced with explanatory note when over limit
- [ ] Template sensor included without filtering
- [ ] Group entity included without filtering
- [ ] Light entity includes brightness attribute
- [ ] Climate entity includes temperature and hvac_mode attributes
- [ ] Entity with no friendly_name uses entity_id
- [ ] Unavailable entity included with "unavailable" state
- [ ] Returns set of exposed entity_ids alongside formatted text
- [ ] Builds fresh context (state change reflected in next call)
- [ ] Performance: < 500ms for 250 entities

---

## Dependencies

### Story Dependencies

| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| [US0001](US0001-project-scaffold.md) | Hard | const.py (MAX_ENTITIES, CONF_CONTEXT_* keys, defaults) | Done |

### External Dependencies

| Dependency | Type | Status |
|------------|------|--------|
| Home Assistant Core 2025.1.0+ | Framework | Available |
| HA voice assistant expose API | Internal API | Available |

---

## Estimation

**Story Points:** 3
**Complexity:** Medium

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-04-05 | Claude | Initial story generation |
