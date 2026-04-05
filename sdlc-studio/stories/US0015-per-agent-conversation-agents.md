# US0015: Per-Agent Conversation Agents

> **Status:** Done
> **Epic:** [EP0004: Multi-Agent Support](../epics/EP0004-multi-agent.md)
> **Owner:** Darren Benson
> **Created:** 2026-04-05

## User Story

**As a** home automation operator with multiple voice satellites
**I want** each bridge agent to appear as a separate conversation agent in HA
**So that** I can assign different agents to different satellites (e.g. Cora for kitchen, Claude for study)

## Context

When `enable_per_agent_entities` is true in the config entry, the integration creates a `conversation.agent_bridge_{agent_id}` entity for each agent that has `chat: true` in the discovery response. Each per-agent conversation agent uses the same entity exposure and room awareness logic as the default conversation agent (US0007), but routes requests via the `agent` field in the API request rather than relying on the bridge's default routing.

---

## Acceptance Criteria

### AC1: Per-agent entity creation
- **Given** `enable_per_agent_entities` is true
- **When** the coordinator discovers agents with `chat: true`
- **Then** a `conversation.agent_bridge_{agent_id}` entity is created for each

### AC2: Non-chat agents excluded
- **Given** `enable_per_agent_entities` is true
- **When** the coordinator discovers an agent with `chat: false`
- **Then** no conversation entity is created for that agent

### AC3: Agent field routing
- **Given** a per-agent conversation entity handles a request
- **When** it sends the request to the bridge API
- **Then** the `agent` field in the POST body is set to the entity's agent_id (not the bridge default)

### AC4: Entity exposure shared
- **Given** a per-agent conversation entity processes a request
- **When** it builds the system prompt context
- **Then** it includes the same entity exposure data (HA state context) as the default conversation agent

### AC5: Room awareness shared
- **Given** a per-agent conversation entity processes a voice request with area context
- **When** it builds the request
- **Then** it includes room/area awareness data identical to the default conversation agent

### AC6: Feature gating
- **Given** `enable_per_agent_entities` is false (default)
- **When** the integration loads
- **Then** no per-agent conversation entities are created

### AC7: Entity naming
- **Given** per-agent entities are created
- **When** viewed in HA
- **Then** each has a friendly name derived from the agent's display name in discovery data

### AC8: Selectable in Assist
- **Given** per-agent conversation entities exist
- **When** configuring a voice satellite's conversation agent
- **Then** each per-agent entity appears in the conversation agent picker

---

## Scope

### In Scope
- Per-agent `ConversationEntity` subclass (or factory) in `conversation.py`
- Routing via `agent` field in chat completion request
- Shared entity exposure and room awareness logic
- Gating behind `enable_per_agent_entities` config flag

### Out of Scope
- Default conversation agent (US0007)
- Per-agent health sensors (US0016)
- Dynamic discovery lifecycle (US0017)
- Entity exposure implementation itself (reused from US0007)

---

## Technical Notes

The per-agent conversation entity should share a base class or mixin with the default conversation agent to avoid duplicating entity exposure and room awareness logic. The key difference is that `_build_request_body()` (or equivalent) sets `"agent": self._agent_id` instead of omitting the field. Entity unique ID should be `{entry.entry_id}_{agent_id}` to ensure stability across restarts. The agent_id must be sanitised for use in entity IDs (lowercase, underscores for special chars).

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| Agent ID contains special characters | Sanitised to valid HA entity ID format |
| enable_per_agent_entities toggled from false to true | Entities created on next coordinator poll cycle |
| enable_per_agent_entities toggled from true to false | Per-agent entities removed |
| Agent has chat:true but is unhealthy | Entity created but may return errors; health is US0016's concern |
| Two agents share same display name | Both get entities; unique IDs differ by agent_id |
| Bridge returns 50+ agents | Entities created for all chat-capable agents (no arbitrary cap) |
| Per-agent entity called while bridge is down | Returns error response, same as default agent behaviour |

---

## Test Scenarios

- [ ] Per-agent entities created for each chat:true agent when enabled
- [ ] No per-agent entities created for chat:false agents
- [ ] No per-agent entities created when enable_per_agent_entities is false
- [ ] Per-agent entity sets agent field in API request body
- [ ] Per-agent entity includes entity exposure context in prompt
- [ ] Per-agent entity includes room awareness data for voice requests
- [ ] Entity unique ID is stable across restarts ({entry_id}_{agent_id})
- [ ] Entity friendly name matches agent display name from discovery
- [ ] Per-agent entities appear in conversation agent picker
- [ ] Special characters in agent_id sanitised for entity ID
- [ ] Toggling enable_per_agent_entities on creates entities
- [ ] Toggling enable_per_agent_entities off removes entities

---

## Dependencies

### Story Dependencies
| Story | Relationship |
|-------|-------------|
| US0007 | Requires default conversation agent with entity exposure and room awareness |

### External Dependencies
| Dependency | Type | Status |
|------------|------|--------|
| Home Assistant Core 2025.1.0+ | Framework | Available |

---

## Estimation

**Story Points:** 3
**Complexity:** Medium

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-04-05 | Claude | Initial story generation |
