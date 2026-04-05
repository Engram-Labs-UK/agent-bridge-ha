# EP0003: Observability & Automation

> **Status:** Done
> **Owner:** Darren Benson
> **Reviewer:** --
> **Created:** 2026-04-05
> **Target Release:** 0.1.0

## Summary

Bridge health sensors for dashboards, event entities for automation triggers, HA services for script-based agent interaction, and voice debug logging. After this epic, Darren can build dashboards showing bridge health and automations that react to agent activity.

## Inherited Constraints

| Source | Type | Constraint | Impact |
|--------|------|------------|--------|
| PRD | Performance | Coordinator poll < 100ms overhead | Sensors must not add polling overhead |
| TRD | Architecture | All sensors via DataUpdateCoordinator | No independent polling per sensor |
| TRD | Architecture | Events via hass.bus.async_fire | Standard HA event pattern |

---

## Business Context

### Problem Statement
No way to monitor bridge health in HA dashboards or trigger automations from agent activity (responses, tool invocations).

**PRD Reference:** [Bridge Health Sensors](../prd.md#bridge-health-sensors)

### Value Proposition
Completes the integration's observability story. Dashboard sensors show at-a-glance bridge status. Event entities enable agent-aware automations.

### Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Bridge status visible in HA | No | sensor.agent_bridge_status reflects actual | E2E dashboard check |
| Automation triggers from agent events | 0 | 4 event types (message, tool, discovered, removed) | Integration test |

---

## Scope

### In Scope
- Sensor platform (`sensor.py`): bridge status (ok/degraded/error), agent count (healthy/total)
- Binary sensor platform (`binary_sensor.py`): bridge connectivity (on/off)
- Event platform (`event.py`): message_received and tool_invoked event entities
- Services (`services.py`, `services.yaml`): send_message, invoke_tool services
- Voice debug logging: conditional info-level logging of voice routing decisions

### Out of Scope
- Per-agent health sensors (EP0004)
- Webhook-based real-time events (EP0005)
- Broadcast service (EP0005)

### Affected Personas
- **Darren (operator):** Builds dashboards and automations

---

## Acceptance Criteria (Epic Level)

- [x] sensor.agent_bridge_status shows ok/degraded/error with version and uptime attributes
- [x] binary_sensor.agent_bridge_connected shows on/off for bridge connectivity
- [x] sensor.agent_bridge_agent_count shows healthy count with total as attribute
- [x] All sensors link to a single "Agent Bridge" device in HA device registry
- [x] event.agent_bridge_message_received fires on agent response
- [x] event.agent_bridge_tool_invoked fires on tool execution with ok/error subtypes
- [x] agent_bridge.send_message service sends to bridge and returns response
- [x] agent_bridge.invoke_tool service invokes tool and returns response
- [x] Services validate agent_id against coordinator's cached agent list
- [x] Voice debug logging shows agent, session, area, device_id when enabled
- [x] ruff lint, ruff format, and mypy pass with zero errors

---

## Dependencies

### Blocked By

| Dependency | Type | Status | Owner |
|------------|------|--------|-------|
| EP0001 | Epic | Done | Darren Benson |
| EP0002 | Epic | Done | Darren Benson |

### Blocking

| Item | Type | Impact |
|------|------|--------|
| EP0004 | Epic | Per-agent sensors extend sensor platform |
| EP0005 | Epic | Broadcast service extends service handler |

---

## Risks & Assumptions

### Assumptions
- HA EventEntity platform is stable in 2025.1.0+
- Coordinator data structure provides all fields needed for sensors

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Event entity platform API changes | Low | Medium | Pin to HA 2025.1.0+ patterns |
| Service response_variable not available in all automation contexts | Low | Low | Document in service descriptions |

---

## Technical Considerations

### Architecture Impact
Establishes entity platform patterns (sensor, binary_sensor, event). All EP0004 per-agent entities extend these.

### Integration Points
- DataUpdateCoordinator (from EP0001)
- HA Entity platform framework
- HA Device registry (single "Agent Bridge" device)
- HA Service registry
- Bridge Client (from EP0001)

---

## Sizing

**Story Points:** 13
**Estimated Story Count:** 4

**Complexity Factors:**
- Three entity platforms (sensor, binary_sensor, event)
- Service handlers with input validation
- Event entity subtypes (tool_invoked_ok, tool_invoked_error)

---

## Story Breakdown

| | ID | Title | Status | Points |
|---|-----|-------|--------|--------|
| [x] | [US0011](../stories/US0011-sensor-platform.md) | Sensor Platform | Done | 2 |
| [x] | [US0012](../stories/US0012-binary-sensor-and-device.md) | Binary Sensor & Device | Done | 2 |
| [x] | [US0013](../stories/US0013-event-platform.md) | Event Platform | Done | 2 |
| [x] | [US0014](../stories/US0014-services-and-voice-debug.md) | Services & Voice Debug Logging | Done | 3 |

**Total:** 4 stories, 9 points

---

## Open Questions

None.

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-04-05 | Claude | Initial epic generation from PRD |
