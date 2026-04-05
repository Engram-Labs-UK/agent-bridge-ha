# US0011: Sensor Platform

> **Status:** Done
> **Epic:** [EP0003: Observability & Automation](../epics/EP0003-observability-and-automation.md)
> **Owner:** Darren Benson
> **Created:** 2026-04-05

## User Story

**As a** home automation operator
**I want** bridge health and agent count sensors in Home Assistant
**So that** I can build dashboards showing bridge status at a glance

## Context

Two sensor entities expose bridge state from coordinator data. `sensor.agent_bridge_status` shows the bridge's health status (ok, degraded, error) with version and uptime attributes. `sensor.agent_bridge_agent_count` shows the number of healthy agents with total count as an attribute. Both sensors read from DataUpdateCoordinator data -- no independent polling.

---

## Acceptance Criteria

### AC1: Bridge status sensor
- **Given** the integration is loaded and coordinator is polling
- **When** the coordinator receives health data from the bridge
- **Then** `sensor.agent_bridge_status` has state "ok", "degraded", or "error" matching the bridge response

### AC2: Bridge status attributes
- **Given** `sensor.agent_bridge_status` exists
- **When** the coordinator updates
- **Then** the sensor has `version` (string) and `uptime` (integer, seconds) as extra state attributes

### AC3: Agent count sensor
- **Given** the integration is loaded and coordinator is polling
- **When** the coordinator receives discovery data
- **Then** `sensor.agent_bridge_agent_count` shows the number of healthy agents as its state

### AC4: Agent count attributes
- **Given** `sensor.agent_bridge_agent_count` exists
- **When** the coordinator updates
- **Then** the sensor has `total` (integer) as an extra state attribute representing the total number of agents regardless of health

### AC5: Coordinator-driven updates
- **Given** both sensors are registered
- **When** the DataUpdateCoordinator fires an update
- **Then** both sensors update their state and attributes from `coordinator.data`
- **And** neither sensor initiates its own HTTP request

### AC6: Device registry linkage
- **Given** both sensors are created
- **When** viewed in the HA device registry
- **Then** both belong to the single "Agent Bridge" device entry

---

## Scope

### In Scope
- `custom_components/agent_bridge/sensor.py`
- Two `SensorEntity` subclasses reading from coordinator data
- Device info linking to shared "Agent Bridge" device

### Out of Scope
- Per-agent sensors (US0016)
- Coordinator implementation (US0005)
- Binary sensor platform (US0012)

---

## Technical Notes

Sensors should subclass `CoordinatorEntity` and `SensorEntity`. The status sensor should use `SensorDeviceClass` of `ENUM` with options `["ok", "degraded", "error"]`. The agent count sensor is a plain integer sensor. Both use `async_setup_entry` to register via the coordinator stored in `hass.data[DOMAIN][entry.entry_id]`.

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| Bridge unreachable (coordinator update fails) | Both sensors become unavailable via coordinator's built-in handling |
| Bridge returns unknown status value | Status sensor shows raw value; no crash |
| Zero agents discovered | Agent count shows 0, total attribute shows 0 |
| Coordinator not yet polled (first load) | Sensors show unavailable until first successful poll |

---

## Test Scenarios

- [ ] sensor.agent_bridge_status state is "ok" when bridge reports healthy
- [ ] sensor.agent_bridge_status state is "degraded" when bridge reports degraded
- [ ] sensor.agent_bridge_status state is "error" when bridge reports error
- [ ] sensor.agent_bridge_status has version attribute matching bridge response
- [ ] sensor.agent_bridge_status has uptime attribute as integer
- [ ] sensor.agent_bridge_agent_count state equals number of healthy agents
- [ ] sensor.agent_bridge_agent_count total attribute equals total agent count
- [ ] Both sensors update when coordinator fires update (no independent polling)
- [ ] Both sensors linked to "Agent Bridge" device in device registry
- [ ] Both sensors unavailable when coordinator update fails

---

## Dependencies

### Story Dependencies
| Story | Relationship |
|-------|-------------|
| [US0005](US0005-coordinator-and-setup.md) | Requires coordinator and CoordinatorData structure |

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
