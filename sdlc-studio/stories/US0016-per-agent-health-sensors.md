# US0016: Per-Agent Health Sensors

> **Status:** Done
> **Epic:** [EP0004: Multi-Agent Support](../epics/EP0004-multi-agent.md)
> **Owner:** Darren Benson
> **Created:** 2026-04-05

## User Story

**As a** home automation operator monitoring multiple agents
**I want** a health binary sensor for each bridge agent
**So that** I can see which agents are healthy and trigger automations when one goes down

## Context

When `enable_per_agent_entities` is true, each agent discovered by the coordinator gets a `binary_sensor.agent_bridge_{agent_id}_healthy` entity. Health data comes from `GET /health?depth=deep`, polled at a 60-second interval (separate from the 30-second shallow health poll). Each sensor shows on (healthy) or off (unhealthy) with attributes exposing adapter type, last response time, and circuit breaker state.

---

## Acceptance Criteria

### AC1: Per-agent binary sensor creation
- **Given** `enable_per_agent_entities` is true
- **When** the coordinator discovers agents
- **Then** a `binary_sensor.agent_bridge_{agent_id}_healthy` entity is created for each agent

### AC2: Healthy state
- **Given** a per-agent health sensor exists
- **When** the deep health check reports the agent as healthy
- **Then** the binary sensor is "on"

### AC3: Unhealthy state
- **Given** a per-agent health sensor exists
- **When** the deep health check reports the agent as unhealthy
- **Then** the binary sensor is "off"

### AC4: Device class
- **Given** a per-agent health sensor exists
- **When** viewed in HA
- **Then** its device class is `connectivity`

### AC5: Attributes
- **Given** a per-agent health sensor exists
- **When** the deep health check updates
- **Then** the sensor has extra state attributes: `adapter_type` (string), `last_response_time` (float, seconds), `circuit_breaker_state` (string: closed/open/half-open)

### AC6: Deep health polling interval
- **Given** the integration is loaded with per-agent entities enabled
- **When** deep health polling runs
- **Then** it calls `GET /health?depth=deep` at a 60-second interval

### AC7: Feature gating
- **Given** `enable_per_agent_entities` is false (default)
- **When** the integration loads
- **Then** no per-agent health sensors are created and no deep health polling occurs

### AC8: Device registry linkage
- **Given** per-agent health sensors are created
- **When** viewed in the HA device registry
- **Then** each belongs to the single "Agent Bridge" device entry

---

## Scope

### In Scope
- Per-agent `BinarySensorEntity` subclasses in `binary_sensor.py`
- Deep health data parsing from coordinator
- 60-second deep health poll (may be a secondary coordinator or timed update within existing coordinator)

### Out of Scope
- Bridge-level binary sensor (US0012)
- Per-agent conversation agents (US0015)
- Dynamic entity lifecycle (US0017)

---

## Technical Notes

The deep health poll could be implemented as a secondary `DataUpdateCoordinator` with a 60-second interval, or as an additional timed fetch within the existing coordinator. The 60-second interval is longer than the 30-second shallow poll because deep health is more expensive on the bridge side. Per-agent sensors should subclass `CoordinatorEntity` and `BinarySensorEntity`. Entity unique ID should be `{entry.entry_id}_{agent_id}_healthy`.

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| Deep health endpoint returns 500 | All per-agent sensors become unavailable via coordinator handling |
| Agent present in discovery but absent from deep health | Sensor shows unavailable (data missing) |
| Agent has no circuit breaker configured | circuit_breaker_state attribute is "none" |
| last_response_time is null (agent never called) | Attribute is null/None |
| enable_per_agent_entities toggled on at runtime | Deep health polling starts, sensors created on next poll |
| enable_per_agent_entities toggled off at runtime | Deep health polling stops, sensors removed |
| 20 agents (max scale) | 20 binary sensors created; single deep health call returns all |

---

## Test Scenarios

- [ ] Per-agent binary sensor created for each agent when enabled
- [ ] No per-agent sensors when enable_per_agent_entities is false
- [ ] Sensor is "on" when agent healthy
- [ ] Sensor is "off" when agent unhealthy
- [ ] Device class is BinarySensorDeviceClass.CONNECTIVITY
- [ ] adapter_type attribute present and correct
- [ ] last_response_time attribute present as float
- [ ] circuit_breaker_state attribute shows closed/open/half-open
- [ ] Deep health polled at 60-second interval
- [ ] Deep health not polled when per-agent entities disabled
- [ ] Sensors linked to "Agent Bridge" device
- [ ] Entity unique ID is {entry_id}_{agent_id}_healthy
- [ ] Sensor unavailable when deep health call fails

---

## Dependencies

### Story Dependencies
| Story | Relationship |
|-------|-------------|
| [US0005](US0005-coordinator-and-setup.md) | Requires coordinator infrastructure |
| [US0012](US0012-binary-sensor-and-device.md) | Extends binary sensor platform and reuses device entry |

### External Dependencies
| Dependency | Type | Status |
|------------|------|--------|
| Home Assistant Core 2025.1.0+ | Framework | Available |

---

## Estimation

**Story Points:** 2
**Complexity:** Low

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-04-05 | Claude | Initial story generation |
