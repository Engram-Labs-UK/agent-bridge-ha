# US0012: Binary Sensor & Device

> **Status:** Done
> **Epic:** [EP0003: Observability & Automation](../epics/EP0003-observability-and-automation.md)
> **Owner:** Darren Benson
> **Created:** 2026-04-05

## User Story

**As a** home automation operator
**I want** a binary sensor showing bridge connectivity and a device entry for the integration
**So that** I can see at a glance whether the bridge is reachable and group all entities under one device

## Context

A single binary sensor `binary_sensor.agent_bridge_connected` indicates whether the bridge is reachable. It uses `device_class: connectivity` so HA renders it correctly (on = connected, off = disconnected). This entity also establishes the "Agent Bridge" device entry in the HA device registry, which all other entities (sensors, events) link to.

---

## Acceptance Criteria

### AC1: Connectivity binary sensor
- **Given** the integration is loaded and coordinator is polling
- **When** the coordinator updates with `connected: true`
- **Then** `binary_sensor.agent_bridge_connected` is "on"

### AC2: Disconnected state
- **Given** the integration is loaded
- **When** the coordinator updates with `connected: false`
- **Then** `binary_sensor.agent_bridge_connected` is "off"

### AC3: Device class
- **Given** `binary_sensor.agent_bridge_connected` exists
- **When** viewed in HA
- **Then** its device class is `connectivity`

### AC4: Coordinator-driven updates
- **Given** the binary sensor is registered
- **When** the DataUpdateCoordinator fires an update
- **Then** the sensor reads `coordinator.data.connected` for its state
- **And** it does not initiate its own HTTP request

### AC5: Device registry entry
- **Given** the integration is loaded
- **When** entities are registered
- **Then** an "Agent Bridge" device exists in the HA device registry with identifiers `(DOMAIN, entry.entry_id)`, manufacturer "Agent Bridge", and model "Bridge"

### AC6: All entities share the device
- **Given** the "Agent Bridge" device entry exists
- **When** sensors from US0011 and events from US0013 register
- **Then** they link to the same device entry via matching `device_info`

---

## Scope

### In Scope
- `custom_components/agent_bridge/binary_sensor.py`
- One `BinarySensorEntity` subclass reading from coordinator data
- Device info definition for the shared "Agent Bridge" device

### Out of Scope
- Per-agent health binary sensors (US0016)
- Sensor platform (US0011)
- Event platform (US0013)

---

## Technical Notes

Subclass `CoordinatorEntity` and `BinarySensorEntity`. The `is_on` property should return `coordinator.data.connected`. Device info should be defined as a property returning `DeviceInfo` with `identifiers={(DOMAIN, entry.entry_id)}`. This same device info pattern must be reused by US0011 and US0013 entities.

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| Coordinator update fails (bridge unreachable) | Binary sensor becomes unavailable via coordinator's built-in handling |
| Bridge returns 200 but health is degraded | Binary sensor is "on" (connected); status sensor (US0011) shows "degraded" |
| First poll not yet completed | Binary sensor is unavailable until first successful coordinator update |
| Integration unloaded | Binary sensor removed, device entry cleaned up if no other config entries reference it |

---

## Test Scenarios

- [ ] binary_sensor.agent_bridge_connected is "on" when coordinator.data.connected is true
- [ ] binary_sensor.agent_bridge_connected is "off" when coordinator.data.connected is false
- [ ] Device class is BinarySensorDeviceClass.CONNECTIVITY
- [ ] Updates only from coordinator (no independent polling)
- [ ] "Agent Bridge" device entry created in device registry
- [ ] Device entry has correct identifiers, manufacturer, and model
- [ ] Binary sensor unavailable when coordinator update fails
- [ ] Entity removed on integration unload

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
