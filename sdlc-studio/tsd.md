# Test Strategy Document

> **Project:** Agent Bridge HA
> **Version:** 0.1.0
> **Last Updated:** 2026-04-05
> **Owner:** Darren Benson

## Overview

Test strategy for Agent Bridge HA, a Home Assistant custom component. The strategy prioritises conversation agent correctness, entity exposure accuracy, and bridge client reliability since these are the core value paths. All bridge interactions are mocked in automated tests -- live bridge testing is manual E2E only.

## Test Objectives

- Verify the bridge client correctly constructs requests and parses responses for all consumed endpoints
- Verify the conversation agent builds prompts with entity context, room awareness, and correct agent routing
- Verify entity exposure formats HA entities with areas, attributes, and respects the 250-entity cap
- Verify the config flow validates bridge connectivity and authentication before accepting config
- Verify the coordinator polls bridge health and updates entity state correctly
- Verify sensors, binary sensors, and event entities reflect coordinator data accurately
- Verify services (send_message, invoke_tool, broadcast) validate inputs and call correct bridge endpoints
- Verify per-agent conversation agents route to the correct bridge agent
- Verify graceful degradation when bridge is unreachable (cached data, user-friendly errors)
- Verify tool execution from agent tool_calls: entity validation, HA service calls, loop cap, batch execution, partial failure handling, and result formatting (P0 critical path)
- Verify session persistence creates, reuses, and survives HA restarts with correct session ID format
- Verify continuation detection triggers on question patterns and suppresses on exclusion phrases
- Verify error responses from the bridge are translated to user-friendly conversation messages

## Scope

### In Scope
- All source modules in `custom_components/agent_bridge/`
- Config flow validation and options flow
- Conversation agent prompt building and response handling
- Entity exposure formatting and capping
- Coordinator polling and caching behaviour
- Sensor, binary sensor, and event entity state
- Service handlers and input validation
- Bridge client HTTP request construction and response parsing
- Error handling and graceful degradation paths

### Out of Scope
- Live Agent Bridge calls (requires running bridge instance)
- Live HA Assist pipeline testing (requires physical voice satellites)
- Agent Bridge internal behaviour (tested in agent-bridge repo)
- HA Core framework bugs (tested by HA Core team)
- HACS installation mechanics
- Performance/load testing (homelab scale, single user)

---

## Test Levels

### Coverage Targets

| Level | Target | Rationale |
|-------|--------|-----------|
| Unit | 90% | Core logic: client, exposure, conversation agent, coordinator |
| Integration | 80% | Config flow round-trips, service calls with mocked bridge |
| E2E | Feature coverage | Every user-visible feature verified manually in homelab |

### Unit Testing

| Attribute | Value |
|-----------|-------|
| Coverage Target | 90% |
| Framework | pytest + pytest-homeassistant-custom-component |
| Execution | `python -m pytest tests/ -v` (pre-commit, CI) |

**What to unit test:**

| Module | Tests | Priority |
|--------|-------|----------|
| `client.py` | Request construction (URL, headers, body), response parsing (nested text extraction, tool_call extraction), error handling (typed exceptions), auth failure detection, timeout, SSL toggle, HA session reuse | P0 |
| `exposure.py` | Entity formatting (name, state, area, attributes), 250-entity cap, truncation strategy, empty state, unavailable entities, template entities and groups pass through without type filtering | P0 |
| `conversation.py` | System prompt building (three-layer: room + entities + extra), agent routing (default vs voice), voice source signalling, device/satellite/area metadata, language passthrough, session persistence, ConversationResult construction, error message mapping, continuation detection | P0 |
| `coordinator.py` | Poll scheduling, data parsing, cache on failure (3 strikes), connected/disconnected transitions, agent diff detection | P0 |
| `config_flow.py` | Step 1 validation (URL format, connectivity, auth), step 2 agent selection, options flow changes | P0 |
| `sensor.py` | State from coordinator data, attribute mapping, unavailable when disconnected | P1 |
| `binary_sensor.py` | Connected state, per-agent health state, device class | P1 |
| `event.py` | Event firing on message received, event firing on tool invocation, event data shape | P1 |
| `tool_executor.py` | HA service call from tool_call, entity validation against exposure list, batch execution, timeout handling, result formatting | P0 |
| `helpers.py` | Recursive text extraction (priority keys, depth limit), text normalisation | P1 |
| `services.py` | Input validation, agent_id lookup, bridge client call, response formatting | P1 |
| `__init__.py` | Integration setup (async_setup_entry, async_unload_entry), platform forwarding | P1 |
| `const.py` | Constant values (domain, platforms, defaults) | P2 |

### Integration Testing

| Attribute | Value |
|-----------|-------|
| Scope | Config flow round-trips, coordinator + entity updates, service calls |
| Framework | pytest + pytest-homeassistant-custom-component |
| Execution | `python -m pytest tests/ -v` (runs with unit tests) |

**Integration test scenarios:**

| Scenario | What it covers |
|----------|---------------|
| Config flow happy path | Enter URL + token → bridge responds healthy → show agents → select defaults → entry created |
| Config flow auth failure | Enter URL + token → bridge returns 401 → show auth error → do not create entry |
| Config flow unreachable | Enter URL → connection refused → show connectivity error |
| Options flow agent change | Change default agent → coordinator picks up change → conversation routes to new agent |
| Coordinator poll cycle | Setup entry → coordinator polls → sensors update → binary sensor connected |
| Coordinator bridge down | Setup entry → bridge goes offline → 3 polls fail → sensors show offline → bridge returns → sensors recover |
| Conversation round-trip | User sends message → conversation agent builds prompt → calls bridge → returns response → fires event |
| Conversation with room | Voice request from device in "Kitchen" area → system prompt includes "The user is in the Kitchen" |
| Conversation with satellite_id | Voice request with satellite_id different from device_id → area resolved from satellite's device entry |
| Conversation voice metadata | Voice request → chat request includes `metadata.source: "voice"`, `metadata.area`, `metadata.device_id` |
| Conversation text input | Text input (no device_id) → chat request has no metadata block (or `source: "text"`) |
| Conversation extra_system_prompt | Pipeline provides extra_system_prompt → included as third layer in system prompt |
| Conversation language passthrough | Voice input with language "de" → IntentResponse.language set to "de" |
| Session persistence create | First conversation with agent "cora" → session ID created and persisted to HA Store |
| Session persistence reuse | Second conversation with same agent → same session ID reused from Store |
| Session persistence restart | HA restarts → session IDs loaded from Store → previous sessions resumed |
| Voice debug logging | debug_logging enabled → info log includes agent, session, area, device_id |
| Voice debug logging off | debug_logging disabled → no routing info logged |
| Tool call execution | Agent returns tool_call execute_service → integration calls hass.services.async_call → tool result sent back → agent gives final response |
| Tool call batch | Agent returns execute_services with 3 entities → all 3 services called → results sent back |
| Tool call validation | Agent targets unexposed entity → tool call rejected with error message to agent |
| Tool call disabled | enable_tool_calls=false → tool_calls in response ignored, only text content used |
| Tool call timeout | HA service call hangs → 10s timeout → error result sent to agent |
| Tool call event | Tool executed → agent_bridge_tool_invoked event fires with entity_id, status, duration |
| Response nested extraction | Bridge returns deeply nested response structure → text extracted via priority key traversal |
| Response tool_calls extraction | Bridge response includes tool_calls array → extracted and processed by conversation agent |
| Auth failure handling | Bridge returns 401 → BridgeAuthError raised → config entry reload triggered |
| Client uses HA session | Client initialised → uses async_get_clientsession() not new aiohttp.ClientSession |
| Conversation bridge error | Bridge returns AGENT_TIMEOUT → conversation returns user-friendly error message |
| Service send_message | Automation calls send_message → bridge receives correct request → response returned |
| Service invoke_tool | Automation calls invoke_tool → bridge receives tool request → response returned |
| Service invalid agent | Service called with unknown agent_id → validation error returned |
| Per-agent entities enabled | Enable per_agent_entities → coordinator discovers 3 agents → 3 conversation agents + 3 binary sensors created |
| Per-agent entity removal | Agent disappears from discovery → entity marked unavailable (not deleted) |
| Entity exposure cap | Expose 300 entities → context contains at most 250 |
| Entity exposure attributes | Expose light at 75% brightness → context includes "brightness: 75" |
| Continuation detection question | Agent response ends with "?" → ConversationResult has continue_conversation=True |
| Continuation detection statement | Agent response ends with "." → ConversationResult has continue_conversation=False |
| Broadcast service | Automation calls broadcast with message → bridge receives POST /v1/broadcast → aggregated response returned |
| Broadcast with tags | Automation calls broadcast with tags filter → bridge receives tags in request body |
| Tool call loop cap | Agent returns tool_calls on every response for 11 rounds → after 10th iteration, user receives "Agent could not complete the request" error |
| Tool call content + tool_calls | Agent returns both content ("I'll turn on the lights") and tool_calls → tools executed first, content preserved in message history, agent gives final grounded response |
| Tool call batch partial failure | Agent returns execute_services with 3 entities, 1 times out → agent receives per-entity results: 2 success + 1 failure → agent reports partial success |
| Template entity exposure | Expose template sensor (binary_sensor.house_occupied) and group (group.kitchen_lights) → both appear in entity context without filtering |
| Unload entry | Remove integration → coordinator stopped → conversation agent unregistered → entities removed |

### End-to-End Testing

| Attribute | Value |
|-----------|-------|
| Scope | Full stack with live bridge and HA instance |
| Framework | Manual testing + curl scripts |
| Execution | After deployment on homeautoserver |

### E2E Feature Coverage Matrix

| Feature Area | Test Method | Status |
|--------------|------------|--------|
| Config flow setup | HA UI: Settings → Add Integration → Agent Bridge | Not Started |
| Voice command (default agent) | Voice satellite: "Turn on the kitchen lights" | Not Started |
| Voice command (per-agent) | Assign Cora to kitchen pipeline, Claude to study | Not Started |
| Room awareness | Voice from kitchen satellite → verify agent receives room context | Not Started |
| Entity exposure | Verify agent can see and control exposed entities | Not Started |
| Bridge health sensor | Dashboard: verify sensor shows ok/degraded/error | Not Started |
| Agent count sensor | Dashboard: verify count matches bridge discovery | Not Started |
| Connectivity sensor | Kill bridge → verify sensor shows disconnected → restart → recovers | Not Started |
| Per-agent health | Enable per-agent entities → verify per-agent binary sensors | Not Started |
| send_message service | Automation: send message to Cora → verify response | Not Started |
| invoke_tool service | Automation: invoke tool on agent → verify response | Not Started |
| Event: message received | Automation: trigger on message_received event → verify fires | Not Started |
| Event: tool invoked | Automation: trigger on tool_invoked event → verify fires | Not Started |
| Options flow | Change default agent → verify conversation routes to new agent | Not Started |
| Graceful degradation | Bridge offline → voice command → user hears "Bridge is offline" | Not Started |
| Multi-turn voice | Agent asks follow-up question → verify HA keeps listening | Not Started |
| Session survives restart | Voice command → restart HA → voice command again → agent has prior context | Not Started |
| Voice vs text routing | Voice from satellite uses voice_agent → text from dashboard uses default_agent | Not Started |
| Voice response format | Voice command → agent response is concise, no markdown (source=voice effect) | Not Started |
| Room-specific command | "Turn on the lights" from kitchen satellite → kitchen lights turn on, not all | Not Started |
| Tool execution (light) | "Turn on the kitchen lights" → agent returns tool_call → light.kitchen turns on → agent confirms | Not Started |
| Tool execution (climate) | "Set heating to 21" → agent returns tool_call → thermostat changes → agent confirms | Not Started |
| Tool execution (multi) | "Turn off everything in the study" → agent batches tool_calls → multiple entities change | Not Started |
| Unexposed entity blocked | Agent tries to control unexposed entity → blocked → agent reports it cannot | Not Started |
| Broadcast service | Automation: broadcast to all agents → verify aggregated responses | Not Started |

---

## Test Environments

| Environment | Purpose | URL | Data |
|-------------|---------|-----|------|
| Local | Development + unit/integration tests | localhost | Mock bridge, HA test fixtures |
| Homelab | Production E2E | 10.0.0.209:8123 | Real bridge (10.0.0.206:18780), real agents |

## Test Data Strategy

### Approach
- Unit tests: inline fixtures, mock bridge responses returning canned JSON
- Integration tests: HA test fixtures (mock config entries, mock entity registries), mock aiohttp responses
- E2E tests: real bridge with real agents on homelab

### Test Doubles

| Component | Test Double | Purpose |
|-----------|------------|---------|
| Bridge API | aiohttp mock (aioresponses) | Return canned health, discovery, chat responses |
| HA entity registry | pytest-homeassistant-custom-component fixtures | Provide mock entities for exposure testing |
| HA device registry | pytest-homeassistant-custom-component fixtures | Provide mock device-to-area mappings |
| HA area registry | pytest-homeassistant-custom-component fixtures | Provide mock area names |
| HA conversation API | Mock ConversationInput | Simulate voice and text input |
| HA service registry | Mock hass.services.async_call | Verify tool executor service calls without real devices |
| HA Store | Mock homeassistant.helpers.storage.Store | Verify session persist/load cycle without filesystem |

### Test Fixtures

| Type | Location | Purpose |
|------|----------|---------|
| Bridge health responses | `tests/fixtures/health/` | Shallow and deep health JSON responses |
| Bridge discovery responses | `tests/fixtures/discovery/` | Agent lists with various health states |
| Bridge chat responses | `tests/fixtures/chat/` | Chat completion responses (success, tool_calls, content+tool_calls, error, timeout) |
| Bridge error responses | `tests/fixtures/errors/` | All BridgeError code variants |
| HA entity states | `tests/fixtures/entities/` | Entity state dicts for exposure testing |
| Config entry data | `tests/conftest.py` | Standard config entry fixtures |

### Sensitive Data
- Test config uses dummy tokens (`test-bridge-token-123`)
- Real tokens only in HA's encrypted config entry on production instance
- No real bridge URLs in test fixtures

---

## Automation Strategy

### Automation Candidates
- All unit tests (pytest, zero external deps)
- All integration tests (HA test framework, mock bridge)
- Config flow validation (mock bridge responses)
- Entity exposure formatting (mock entity registries)
- Error handling paths (mock bridge errors)

### Manual Testing
- Voice satellite interaction (requires physical hardware)
- HA Assist pipeline configuration (requires HA UI)
- HACS installation (requires live HACS instance)
- Dashboard sensor display (requires HA frontend)
- Multi-turn voice dialogue (requires voice hardware)
- Bridge failover behaviour (requires live bridge restart)

### Automation Framework Stack

| Layer | Tool | Language |
|-------|------|----------|
| Unit | pytest | Python |
| Integration | pytest + pytest-homeassistant-custom-component | Python |
| E2E | curl scripts + manual | Bash |
| Coverage | pytest-cov (coverage.py) | N/A |
| Mocking | unittest.mock + aioresponses | Python |

---

## CI/CD Integration

### Pipeline Stages

1. **Pre-commit:** ruff lint + format check, mypy type check
2. **PR:** Unit + integration tests, coverage check
3. **Merge to main:** Full test suite
4. **Release:** Tag → HACS picks up new version automatically

### Quality Gates

| Gate | Criteria | Blocking |
|------|----------|----------|
| ruff lint | Zero errors | Yes |
| mypy type check | Zero errors | Yes |
| Unit coverage | >= 90% | Yes |
| Integration tests | 100% pass | Yes |
| Config flow tests | All paths tested | Yes |

### Performance Targets (from PRD NFRs)

| Target | Threshold | Measurement | Blocking |
|--------|-----------|-------------|----------|
| Entity context build | < 500ms for 250 entities | Timed in test | Yes |
| Coordinator poll | < 100ms per cycle | Timed in test | No (advisory) |

---

## Defect Management

### Severity Definitions

| Severity | Definition | SLA |
|----------|------------|-----|
| Critical | Conversation agent broken, cannot control home via voice | Immediate fix |
| High | Entity exposure wrong (agent sees stale/incorrect state) | Same day |
| Medium | Sensor shows incorrect data, service returns wrong format | Next session |
| Low | Minor issue (translation, attribute formatting) | Backlog |

---

## Tools and Infrastructure

| Purpose | Tool |
|---------|------|
| Test runner | pytest |
| HA test fixtures | pytest-homeassistant-custom-component |
| HTTP mocking | aioresponses |
| Coverage | pytest-cov (coverage.py) |
| Linting | ruff |
| Type checking | mypy |
| CI/CD | GitHub Actions |

---

## Test Organisation

```text
tests/
  conftest.py                    # Shared fixtures: config entries, mock bridge, mock entities
  fixtures/
    health/
      shallow_ok.json
      shallow_degraded.json
      deep_all_healthy.json
      deep_mixed.json
    discovery/
      three_agents.json
      empty.json
      agent_added.json
      agent_removed.json
    chat/
      success.json
      tool_calls.json               # Response with tool_calls array
      content_and_tool_calls.json   # Response with both content and tool_calls
      timeout_error.json
      circuit_open_error.json
    errors/
      auth_required.json
      rate_limited.json
      agent_unreachable.json
    entities/
      lights_and_sensors.py        # Mock entity states
      empty_home.py
  test_client.py                   # Bridge client HTTP tests
  test_config_flow.py              # Config flow + options flow
  test_conversation.py             # Conversation agent + prompt building
  test_coordinator.py              # Polling, caching, degradation
  test_exposure.py                 # Entity exposure formatting
  test_sensor.py                   # Sensor entity state
  test_binary_sensor.py            # Binary sensor state
  test_event.py                    # Event entity firing
  test_services.py                 # Service handlers
  test_tool_executor.py            # HA service execution from tool_calls
  test_helpers.py                  # Text extraction, normalisation
  test_init.py                     # Integration setup/unload
```

---

## Related Specifications

- [Product Requirements Document](prd.md)
- [Technical Requirements Document](trd.md)

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-04-05 | Darren Benson | Initial TSD -- greenfield test strategy |
| 2026-04-05 | Claude | RV0001 review: added continuation detection and broadcast integration test scenarios; promoted entity context build to blocking quality gate; added __init__.py to unit test module table |
| 2026-04-05 | Claude | TSD review: added tool execution/session/continuation test objectives; added 4 ADR-005 integration scenarios (loop cap, content+tool_calls, batch partial failure, template exposure); added tool_calls fixtures; added HA service registry and HA Store test doubles; added broadcast E2E scenario |
| 2026-04-05 | Claude | RV0005: test suite implemented -- 188 tests, 90% coverage. 11 test files created. CI/CD pipeline created (.github/workflows/validate.yml) |
