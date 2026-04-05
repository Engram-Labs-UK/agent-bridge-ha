# EP0001: Bridge Foundation

> **Status:** Done
> **Owner:** Darren Benson
> **Reviewer:** --
> **Created:** 2026-04-05
> **Target Release:** 0.1.0

## Summary

Establish the foundational infrastructure for the Agent Bridge HA integration: the async HTTP client that speaks the bridge REST API, the config flow for UI-driven setup, and the DataUpdateCoordinator for health polling. Every other epic depends on this one.

## Inherited Constraints

| Source | Type | Constraint | Impact |
|--------|------|------------|--------|
| PRD | Performance | Bridge client timeout 120s default | Client must support configurable timeouts |
| PRD | Security | Token never logged or exposed | Client must redact auth headers in any debug output |
| TRD | Architecture | Thin adapter -- no bridge logic duplication | Client wraps bridge API, does not add retry/routing logic |
| TRD | Tech Stack | No new pip dependencies | aiohttp and voluptuous only (HA-bundled) |

---

## Business Context

### Problem Statement
There is no standardised way for Home Assistant to communicate with the Agent Bridge. REST sensors and commands exist but are fragile and single-purpose.

**PRD Reference:** [Bridge Client](../prd.md#bridge-client)

### Value Proposition
A single, well-tested HTTP client with config flow gives every subsequent feature a reliable foundation. Without it, nothing else works.

### Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Bridge connectivity validation | None | < 5s in config flow | Timed in config flow step 1 |
| Health poll overhead | N/A | < 100ms per cycle | Timed in coordinator update |
| Auth error detection | None | Immediate (401/403) | Unit test |

---

## Scope

### In Scope
- Bridge Client (`client.py`): async aiohttp client with discover, chat, health, invoke_tool, check_alive methods
- Response text extraction (`helpers.py`): recursive traversal of nested response structures
- Config Flow (`config_flow.py`): two-step UI setup (URL+token, then agent selection) plus options flow
- Data Coordinator (`coordinator.py`): DataUpdateCoordinator for bridge health and discovery polling
- Constants (`const.py`): domain, platform list, config keys, defaults, event types
- Integration setup (`__init__.py`): async_setup_entry, async_unload_entry, platform forwarding, session management
- Manifest (`manifest.json`): HA integration manifest for HACS compatibility
- Translations (`strings.json`, `translations/en.json`): config flow and options flow strings

### Out of Scope
- Conversation agent registration (EP0002)
- Entity exposure (EP0002)
- Sensor/binary_sensor/event platforms (EP0003)
- HA services (EP0003)
- Per-agent entities (EP0004)

### Affected Personas
- **Darren (operator):** First touchpoint -- sets up the integration via config flow

---

## Acceptance Criteria (Epic Level)

- [x] Config flow completes end-to-end: enter URL + token, validate connectivity and auth, select agents, create config entry
- [x] Options flow allows changing all configurable settings post-setup
- [x] Bridge client successfully calls all 5 endpoints (health, health?depth=shallow, health?depth=deep, discovery, chat)
- [x] Coordinator polls bridge health at 30s intervals and discovery at 5min intervals
- [x] Coordinator caches last-known-good data for 3 consecutive failures
- [x] Response text extraction handles nested structures up to 8 levels deep
- [x] Auth failure (401/403) triggers config entry reload notification
- [x] All typed exceptions (BridgeConnectionError, BridgeAuthError, BridgeTimeoutError) raised correctly
- [x] Integration loads and unloads cleanly without resource leaks
- [x] ruff lint, ruff format, and mypy pass with zero errors

---

## Dependencies

### Blocked By

| Dependency | Type | Status | Owner |
|------------|------|--------|-------|
| None | -- | -- | -- |

### Blocking

| Item | Type | Impact |
|------|------|--------|
| EP0002 | Epic | Conversation agent needs bridge client and coordinator |
| EP0003 | Epic | Sensors need coordinator data |
| EP0004 | Epic | Per-agent entities need discovery data |
| EP0005 | Epic | Webhooks and broadcast need bridge client |
| EP0006 | Epic | Streaming needs bridge client |

---

## Risks & Assumptions

### Assumptions
- Agent Bridge REST API is stable (v3.1.0+)
- HA's aiohttp session works for all bridge endpoints (no custom session config needed)
- pytest-homeassistant-custom-component provides adequate test fixtures

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Bridge API changes break client | Low | High | Pin to bridge v3.1.0+ contract, version check in discovery |
| HA aiohttp session has unexpected limitations | Low | Medium | Test with real HA session in integration tests |
| Config flow validation too slow on poor network | Medium | Low | Timeout at 5s, show clear error on timeout |

---

## Technical Considerations

### Architecture Impact
Creates the `custom_components/agent_bridge/` directory structure. Establishes patterns for all subsequent modules: error handling, typed data classes, config entry access.

### Integration Points
- Agent Bridge REST API (all endpoints in TRD Section 5)
- HA ConfigFlow framework
- HA DataUpdateCoordinator
- HA shared aiohttp session (`async_get_clientsession`)
- HA Store for session persistence

---

## Sizing

**Story Points:** 13
**Estimated Story Count:** 5

**Complexity Factors:**
- Config flow has two steps plus options flow (multi-step UI)
- Coordinator has dual polling intervals (health vs discovery)
- Response text extraction needs recursive traversal
- Foundation must be right -- all other epics depend on it

---

## Story Breakdown

| | ID | Title | Status | Points |
|---|-----|-------|--------|--------|
| [x] | [US0001](../stories/US0001-project-scaffold.md) | Project Scaffold | Done | 2 |
| [x] | [US0002](../stories/US0002-bridge-client.md) | Bridge Client | Done | 5 |
| [x] | [US0003](../stories/US0003-response-helpers.md) | Response Helpers | Done | 2 |
| [x] | [US0004](../stories/US0004-config-flow.md) | Config Flow | Done | 3 |
| [x] | [US0005](../stories/US0005-coordinator-and-setup.md) | Data Coordinator & Integration Setup | Done | 3 |

**Total:** 5 stories, 15 points

---

## Open Questions

None -- all foundation decisions made in TRD (ADR-001 through ADR-005).

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-04-05 | Claude | Initial epic generation from PRD |
