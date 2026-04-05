# US0017: Dynamic Agent Discovery

> **Status:** Done
> **Epic:** [EP0004: Multi-Agent Support](../epics/EP0004-multi-agent.md)
> **Owner:** Darren Benson
> **Created:** 2026-04-05

## User Story

**As a** home automation operator
**I want** HA to automatically detect when agents are added or removed from the bridge
**So that** new agents get entities without restarting HA, and removed agents are marked unavailable

## Context

On each discovery poll cycle (every 5 minutes via the coordinator), the integration compares the current agent list against the previous one. New agents trigger entity creation (conversation + health sensor, if per-agent enabled). Removed agents have their entities marked unavailable rather than deleted, preserving automation references. Changed agents (e.g. display name update) have their entity attributes updated. Discovery events fire for additions and removals.

---

## Acceptance Criteria

### AC1: New agent detection
- **Given** `enable_per_agent_entities` is true and the coordinator polls discovery
- **When** a new agent appears in the discovery response that was not in the previous poll
- **Then** `conversation.agent_bridge_{agent_id}` and `binary_sensor.agent_bridge_{agent_id}_healthy` entities are created

### AC2: Removed agent detection
- **Given** per-agent entities exist for an agent
- **When** the agent disappears from the discovery response
- **Then** its entities are marked unavailable (not deleted from the entity registry)

### AC3: Changed agent detection
- **Given** per-agent entities exist for an agent
- **When** the agent's attributes change (e.g. display name, capabilities)
- **Then** the entity attributes are updated to reflect the new values

### AC4: Agent discovered event
- **Given** a new agent is detected
- **When** entities are created for it
- **Then** an `agent_bridge_agent_discovered` event fires on `hass.bus` with `agent_id`, `display_name`, and `capabilities`

### AC5: Agent removed event
- **Given** an agent disappears from discovery
- **When** its entities are marked unavailable
- **Then** an `agent_bridge_agent_removed` event fires on `hass.bus` with `agent_id`

### AC6: No entity creation when disabled
- **Given** `enable_per_agent_entities` is false
- **When** new agents appear in discovery
- **Then** no per-agent entities are created (but discovery events still fire)

### AC7: Stable across restarts
- **Given** per-agent entities were created before a restart
- **When** HA restarts and the coordinator polls
- **Then** existing entities reconnect to their coordinator data (no duplication, no unnecessary discovered events)

---

## Scope

### In Scope
- Discovery diff logic in `coordinator.py` (compare current vs previous agent list)
- Dynamic entity creation via `async_add_entities` callback
- Marking entities unavailable when agents removed
- Updating entity attributes when agents change
- Firing `agent_bridge_agent_discovered` and `agent_bridge_agent_removed` bus events

### Out of Scope
- Webhook-based instant discovery (EP0005)
- The entity implementations themselves (US0015, US0016)
- Coordinator polling mechanism (US0005)

---

## Technical Notes

The coordinator should store the previous agent set (by agent_id) and compare on each discovery update. New agents are those present in current but not previous. Removed agents are those in previous but not current. Changed agents are those in both but with differing attributes.

For dynamic entity creation, the platform `async_setup_entry` should store its `async_add_entities` callback so the coordinator can call it when new agents appear. For marking entities unavailable, set `self._attr_available = False` and call `self.async_write_ha_state()`.

Discovery events are raw `hass.bus.async_fire` events (not EventEntity), since they are operational signals rather than user-facing automation triggers.

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| Agent removed then re-added within same poll | Treated as present (no removal event) |
| Agent removed then re-added across two polls | Removal event on first poll, discovered event on second; entity marked available again |
| All agents removed simultaneously | All per-agent entities marked unavailable; individual removal events fire for each |
| Discovery endpoint returns empty list | All agents treated as removed |
| Discovery endpoint fails (HTTP error) | Previous agent list preserved; no changes applied; coordinator marks update as failed |
| 10 new agents in single poll cycle | 10 conversation + 10 health entities created; 10 discovered events fire |
| Agent ID collision (reused ID, different agent) | Existing entity updated with new attributes; no duplication |
| First poll after integration setup | All agents treated as new; discovered events fire for each |
| HA restart with same agent set | Entities reconnect; no discovered/removed events fire |

---

## Test Scenarios

- [ ] New agent in discovery creates conversation entity (when per-agent enabled)
- [ ] New agent in discovery creates health binary sensor (when per-agent enabled)
- [ ] Removed agent's entities marked unavailable (not deleted)
- [ ] Changed agent's entity attributes updated
- [ ] agent_bridge_agent_discovered event fires with correct agent_id and display_name
- [ ] agent_bridge_agent_removed event fires with correct agent_id
- [ ] No per-agent entities created when enable_per_agent_entities is false
- [ ] Discovery events still fire when per-agent entities disabled
- [ ] Discovery failure preserves previous agent list
- [ ] No spurious events on HA restart with unchanged agent set
- [ ] Re-added agent's entities marked available again
- [ ] Multiple simultaneous additions handled correctly
- [ ] Multiple simultaneous removals handled correctly
- [ ] Agent with changed display name updates entity friendly name

---

## Dependencies

### Story Dependencies
| Story | Relationship |
|-------|-------------|
| [US0005](US0005-coordinator-and-setup.md) | Discovery polling infrastructure and coordinator data |
| [US0015](US0015-per-agent-conversation-agents.md) | Per-agent conversation entity implementation |
| [US0016](US0016-per-agent-health-sensors.md) | Per-agent health sensor implementation |

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
