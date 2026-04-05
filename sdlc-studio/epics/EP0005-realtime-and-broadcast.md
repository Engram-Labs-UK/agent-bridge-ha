# EP0005: Real-Time & Broadcast

> **Status:** Done
> **Owner:** Darren Benson
> **Reviewer:** --
> **Created:** 2026-04-05
> **Target Release:** 0.2.0

## Summary

Phase 2 features: webhook integration for real-time bridge events (replacing polling for instant health updates) and broadcast service for sending messages to multiple agents at once.

## Inherited Constraints

| Source | Type | Constraint | Impact |
|--------|------|------------|--------|
| TRD | Architecture | Webhooks deferred to Phase 2 (ADR-002) | Falls back to polling if registration fails |
| PRD | Availability | Graceful degradation | Webhook failure must not break existing polling |

---

## Business Context

### Problem Statement
Polling at 30s intervals means agent health changes take up to 30s to appear in HA. Broadcast requires per-agent automations.

**PRD Reference:** [Webhook Integration](../prd.md#webhook-integration)

### Value Proposition
Instant health updates without polling delay. Single-call broadcast simplifies system-wide agent instructions.

### Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Health update latency | Up to 30s (polling) | < 2s (webhook) | Timed from bridge event to HA sensor update |
| Broadcast efficiency | N automations for N agents | 1 service call | Automation simplification |

---

## Scope

### In Scope
- Webhook registration with bridge on setup
- HA webhook endpoint to receive bridge events
- Webhook refresh on HA restart
- Graceful fallback to polling if webhook fails
- Webhook unregistration on integration unload
- Broadcast service (agent_bridge.broadcast)

### Out of Scope
- Polling replacement (webhooks supplement, not replace)
- Per-agent webhooks (bridge-level events only)

### Affected Personas
- **Darren (operator):** Faster health updates, simpler broadcast automations

---

## Acceptance Criteria (Epic Level)

- [x] Webhook registered with bridge on setup (POST /v1/webhooks)
- [x] HA webhook endpoint receives bridge events and updates coordinator data
- [x] Webhook refreshed on HA restart
- [x] Falls back to polling if webhook registration fails
- [x] Webhook unregistered on integration unload
- [x] agent_bridge.broadcast service sends to all or tagged agents
- [x] Broadcast returns aggregated responses
- [x] ruff lint, ruff format, and mypy pass with zero errors

---

## Dependencies

### Blocked By

| Dependency | Type | Status | Owner |
|------------|------|--------|-------|
| EP0001 | Epic | Done | Darren Benson |
| EP0003 | Epic | Done | Darren Benson |

### Blocking

| Item | Type | Impact |
|------|------|--------|
| None | -- | -- |

---

## Risks & Assumptions

### Assumptions
- Bridge webhook API (POST /v1/webhooks) is implemented and stable
- HA can receive inbound webhooks from local network

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| HA not reachable from bridge (network topology) | Medium | Medium | Graceful fallback to polling |
| Webhook registration fails silently | Low | Medium | Health check on webhook endpoint, log warning |

---

## Technical Considerations

### Architecture Impact
Adds webhook handling to the integration. Coordinator gains an alternative data path alongside polling.

### Integration Points
- Bridge webhook API (POST /v1/webhooks, DELETE /v1/webhooks/:id)
- Bridge broadcast API (POST /v1/broadcast)
- HA webhook framework
- DataUpdateCoordinator (webhook updates coordinator data directly)

---

## Sizing

**Story Points:** 8
**Estimated Story Count:** 2

**Complexity Factors:**
- Webhook lifecycle management (register, refresh, unregister)
- Network topology uncertainty (HA reachability)

---

## Story Breakdown

| | ID | Title | Status | Points |
|---|-----|-------|--------|--------|
| [x] | [US0018](../stories/US0018-webhook-integration.md) | Webhook Integration | Done | 3 |
| [x] | [US0019](../stories/US0019-broadcast-service.md) | Broadcast Service | Done | 2 |

**Total:** 2 stories, 5 points

---

## Open Questions

None.

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-04-05 | Claude | Initial epic generation from PRD |
