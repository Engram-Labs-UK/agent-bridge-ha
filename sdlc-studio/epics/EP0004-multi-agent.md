# EP0004: Multi-Agent Support

> **Status:** Done
> **Owner:** Darren Benson
> **Reviewer:** --
> **Created:** 2026-04-05
> **Target Release:** 0.1.0

## Summary

When `enable_per_agent_entities` is enabled, each bridge agent gets its own conversation agent entity and health sensor. Dynamic discovery detects when agents are added or removed from the bridge and updates HA entities accordingly.

## Inherited Constraints

| Source | Type | Constraint | Impact |
|--------|------|------------|--------|
| PRD | Scalability | Up to 20 bridge agents | Entity creation must scale to 20 agents |
| TRD | Architecture | Per-agent entities opt-in (ADR-003) | Gated behind enable_per_agent_entities flag |

---

## Business Context

### Problem Statement
Only one conversation agent (the default) is available. Darren cannot assign different agents to different voice satellites (e.g. Cora for kitchen, Claude for study).

**PRD Reference:** [Per-Agent Conversation Agents](../prd.md#per-agent-conversation-agents)

### Value Proposition
Multi-satellite homes get per-room agent assignment. Each agent appears as a selectable conversation agent in HA.

### Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Agents selectable in Assist | 1 (default) | All chat-capable agents | E2E pipeline config |
| Agent health visibility | Bridge-level only | Per-agent binary sensors | Dashboard check |

---

## Scope

### In Scope
- Per-agent conversation agents: conversation.agent_bridge_{agent_id} entities
- Per-agent health sensors: binary_sensor.agent_bridge_{agent_id}_healthy
- Dynamic agent discovery: detect add/remove on each discovery poll cycle
- Discovery events: agent_bridge_agent_discovered, agent_bridge_agent_removed

### Out of Scope
- Default conversation agent (EP0002)
- Bridge-level sensors (EP0003)
- Webhook-based discovery (EP0005)

### Affected Personas
- **Darren (operator):** Assigns agents to satellites, monitors per-agent health

---

## Acceptance Criteria (Epic Level)

- [x] When enabled, each agent with `chat: true` gets a conversation agent entity
- [x] Each per-agent conversation agent routes via `agent` field (not bridge default)
- [x] Per-agent binary sensors show healthy/unhealthy from deep health check
- [x] New agents create entities within one discovery poll cycle
- [x] Removed agents' entities marked unavailable (not deleted)
- [x] Changed agents update entity attributes
- [x] agent_bridge_agent_discovered and agent_bridge_agent_removed events fire
- [x] ruff lint, ruff format, and mypy pass with zero errors

---

## Dependencies

### Blocked By

| Dependency | Type | Status | Owner |
|------------|------|--------|-------|
| EP0001 | Epic | Done | Darren Benson |
| EP0002 | Epic | Done | Darren Benson |
| EP0003 | Epic | Done | Darren Benson |

### Blocking

| Item | Type | Impact |
|------|------|--------|
| None | -- | -- |

---

## Risks & Assumptions

### Assumptions
- Bridge agent IDs are stable (don't change between restarts)
- HA supports dynamic entity creation/removal at runtime

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Entity churn if agents restart frequently | Medium | Low | Mark unavailable rather than delete |
| Too many entities clutter HA UI | Low | Low | Opt-in flag, only chat-capable agents |

---

## Technical Considerations

### Architecture Impact
Extends conversation agent and binary sensor platforms with dynamic entity lifecycle management.

### Integration Points
- Coordinator discovery data (from EP0001)
- Conversation Agent pattern (from EP0002)
- Binary Sensor platform (from EP0003)
- HA entity registry for dynamic add/remove

---

## Sizing

**Story Points:** 8
**Estimated Story Count:** 3

**Complexity Factors:**
- Dynamic entity lifecycle (create, update, mark unavailable)
- Deep health polling (60s interval, separate from shallow)

---

## Story Breakdown

| | ID | Title | Status | Points |
|---|-----|-------|--------|--------|
| [x] | [US0015](../stories/US0015-per-agent-conversation-agents.md) | Per-Agent Conversation Agents | Done | 3 |
| [x] | [US0016](../stories/US0016-per-agent-health-sensors.md) | Per-Agent Health Sensors | Done | 2 |
| [x] | [US0017](../stories/US0017-dynamic-agent-discovery.md) | Dynamic Agent Discovery | Done | 3 |

**Total:** 3 stories, 8 points

---

## Open Questions

None.

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-04-05 | Claude | Initial epic generation from PRD |
