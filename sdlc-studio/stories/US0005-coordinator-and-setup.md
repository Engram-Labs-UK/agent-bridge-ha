# US0005: Data Coordinator & Integration Setup

> **Status:** Done
> **Epic:** [EP0001: Bridge Foundation](../epics/EP0001-bridge-foundation.md)
> **Owner:** Darren Benson
> **Created:** 2026-04-05

## User Story

**As the** integration
**I want** periodic bridge health polling and proper setup/teardown lifecycle
**So that** HA entities stay up to date and resources are cleaned up

## Context

DataUpdateCoordinator polls bridge health (30s) and discovery (5min). The __init__.py setup creates the client, coordinator, and forwards entity platforms. Teardown stops the coordinator and unregisters agents.

---

## Acceptance Criteria

### AC1: Health polling
- **Given** a configured integration
- **When** the coordinator polls
- **Then** it calls GET /health?depth=shallow every 30 seconds and updates CoordinatorData

### AC2: Discovery polling
- **Given** a configured integration
- **When** 5 minutes have elapsed
- **Then** the coordinator calls GET /v1/discovery and updates the agent list

### AC3: Graceful degradation
- **Given** the bridge goes offline
- **When** 3 consecutive polls fail
- **Then** the coordinator marks connected=False but retains last-known-good data for the first 3 failures

### AC4: Integration setup
- **Given** a config entry
- **When** async_setup_entry is called
- **Then** it creates BridgeClient, creates Coordinator, starts polling, and forwards sensor/binary_sensor/event platforms

### AC5: Integration teardown
- **Given** a loaded integration
- **When** async_unload_entry is called
- **Then** it stops the coordinator, unloads platforms, and returns True

### AC6: Typed coordinator data
- **Given** a successful poll
- **When** coordinator.data is accessed
- **Then** it returns CoordinatorData with connected, bridge_status, bridge_version, bridge_uptime, agent_count_healthy, agent_count_total, agents, last_poll

---

## Scope

### In Scope
- `custom_components/agent_bridge/coordinator.py` - AgentBridgeCoordinator
- `custom_components/agent_bridge/__init__.py` - Full setup/teardown (replaces stubs from US0001)
- CoordinatorData TypedDict
- Dual polling intervals (health 30s, discovery 5min)
- 3-strike caching on failure

### Out of Scope
- Sensor entities reading coordinator data (EP0003)
- Session persistence (EP0002 US0009)
- Conversation agent registration (EP0002)

---

## Technical Notes

Coordinator extends `DataUpdateCoordinator[CoordinatorData]`. The dual interval requires tracking last_discovery_poll separately -- main update interval is 30s, but discovery only runs when 5min has elapsed since last discovery poll. Store coordinator on hass.data[DOMAIN][entry.entry_id]. The __init__.py must also create the BridgeClient using async_get_clientsession(hass).

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| Bridge returns degraded status | CoordinatorData.bridge_status = "degraded", connected = True |
| First poll fails (bridge never reached) | connected = False, no cached data, entities show unavailable |
| Bridge recovers after 3 failures | connected = True, fresh data replaces cached |
| Config entry updated (options flow) | Coordinator restarts with new settings |
| HA shutdown during poll | Poll cancelled cleanly, no resource leak |

---

## Test Scenarios

- [ ] Coordinator polls at 30s intervals
- [ ] Coordinator calls health?depth=shallow on each poll
- [ ] Coordinator calls discovery every 5 minutes
- [ ] CoordinatorData has all required fields after successful poll
- [ ] 1 failure: connected still True, cached data used
- [ ] 2 failures: connected still True, cached data used
- [ ] 3 failures: connected = False
- [ ] Bridge recovery: connected = True after next successful poll
- [ ] async_setup_entry creates client and coordinator
- [ ] async_setup_entry forwards platforms
- [ ] async_unload_entry stops coordinator
- [ ] async_unload_entry unloads platforms
- [ ] async_unload_entry returns True

---

## Dependencies

### Story Dependencies

| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| [US0001](US0001-project-scaffold.md) | Hard | const.py, __init__.py stubs | Done |
| [US0002](US0002-bridge-client.md) | Hard | BridgeClient class | Done |

---

## Estimation

**Story Points:** 3
**Complexity:** Medium

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-04-05 | Claude | Initial story generation |
