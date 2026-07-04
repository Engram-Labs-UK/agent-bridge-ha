# Test Strategy Document

> **Project:** Agent Bridge HA
> **Version:** 0.11.1
> **Last Updated:** 2026-07-04
> **Owner:** Darren Benson
> **Last Review:** 2026-07-04 — CR-0011 full reconcile against the shipped suite

> **Currency note (CR-0011, 2026-07-04).** This TSD was fully reconciled against the
> shipped test suite: the test tree and module table below match `tests/` exactly, the
> tool-execution objective and its deleted test files are gone (CR-0006), and the
> approach for the usage/doctor/memory/diagnostics/contract suites plus the CR-0014
> (webhook hardening) and BG0012 (streaming confirm-marker strip) regression suites is
> documented. Mocks are pinned to the v4.36+ bridge shapes (US0022/US0023); CI runs
> ruff + pytest against the pinned HA **2026.2.3** / Python **3.13** and is green.
> The 2026-06-01 audit gaps that drove the re-pin are [CR-0002](change-requests/cr0002.md)
> / [EP0007](epics/EP0007-bridge-v436-modern-ha-realignment.md).

## Overview

Test strategy for Agent Bridge HA, a Home Assistant custom component. The strategy prioritises conversation agent correctness, entity exposure accuracy, and bridge client reliability since these are the core value paths. All bridge interactions are mocked in automated tests -- live bridge testing is manual E2E only.

## Test Objectives

- Verify the bridge client correctly constructs requests and parses responses for all consumed endpoints (including URL-encoded path parameters — CR-0015)
- Verify the consumed endpoint set against a captured slice of the bridge OpenAPI spec (contract testing — CR-0008)
- Verify the conversation entity builds the layered prompt (instructions + source block + grounding hint + extra), the `caller_context` envelope, and correct agent routing via `_async_handle_message`/`ChatLog`
- Verify entity exposure formats HA entities with areas, attributes, and respects the 250-entity cap
- Verify the config flow validates bridge connectivity and authentication before accepting config (including the first-run SSL toggle — CR-0016), and the subentry/options flows
- Verify the coordinator polls bridge health/discovery/usage/doctor and updates entity state correctly
- Verify sensors (including the per-agent usage/cost sensors), binary sensors, and event entities reflect coordinator data accurately
- Verify services (send_message, invoke_tool, broadcast, ask_with_image, announce, memory_record, memory_recall) validate inputs, fall back to the default agent, and call correct bridge endpoints (`ServiceValidationError` semantics — CR-0016)
- Verify per-agent conversation entities route to the correct bridge agent and are gated on voice capability (US0028/CR-0003)
- Verify graceful degradation when bridge is unreachable (cached data, usage/doctor carry-forward, user-friendly errors)
- Verify the actuation boundary: no HA-side tool loop; the actuation audit event fires per reactive turn; the `[confirm:LEVEL]` marker is stripped and surfaced — on both the non-streaming and streaming paths (US0036/BG0012)
- Verify session continuity: idle-windowed channel keys rotate after the idle gap and on clock jumps, and prune stale scopes (US0032)
- Verify webhook hardening: persistent id reuse, stale-subscription cleanup, local-only/POST-only registration, and push validation (status whitelist, typed agentId/healthy — CR-0014)
- Verify drift defences: agent-context baseline check and the opt-in fleet-doctor repair issue (US0029/CR-0009/CR-0012)
- Verify the diagnostics download includes the doctor/usage/agent view with the token redacted (CR-0009)
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

**What to unit test (module ↔ test-file map):**

| Module | Covered by | Tests | Priority |
|--------|-----------|-------|----------|
| `client.py` | `test_client.py`, `test_streaming.py`, `test_openapi_contract.py` | Request construction (URL, headers incl. `x-bridge-mcp-caller`, body), path-parameter URL-encoding (CR-0015), response parsing, typed exceptions (auth/caller/timeout/connection), SSL toggle, HA session reuse, v4.36 SSE frame parsing + legacy fallback, usage/doctor/memory/agent-context/webhook methods, consumed-endpoint contract | P0 |
| `exposure.py` | `test_exposure.py` | Entity formatting (name, state, area, attributes), 250-entity cap, truncation, empty state, unavailable entities, template entities and groups pass through without type filtering, recent-changes summary (US0034) | P0 |
| `conversation.py` | `test_conversation.py`, `test_conversation_integration.py`, `test_streaming.py`, `test_agent_selection.py` | Layered system prompt, `caller_context` envelope, source-type classification, location/floor resolution, session-channel rotation (US0032), voice-capability gating, confirm-marker parse/strip (US0036) incl. the streaming delta adapter (BG0012), audit + message events, ConversationResult, error message mapping, continuation detection | P0 |
| `coordinator.py` | `test_coordinator.py`, `test_drift_surface.py` | Poll scheduling, v4.x agent parsing (health block, taxonomy, crew), tri-state /v1/health enrichment, usage/doctor refresh + carry-forward (BG0007/BG0008), cache on failure (3 strikes), connected/disconnected transitions, agent diff events, webhook push validation (CR-0014) | P0 |
| `config_flow.py` | `test_config_flow.py`, `test_agent_selection.py` | Step 1 validation (connectivity, auth, first-run SSL toggle — CR-0016), step 2 crew-labelled agent selection, options flow (Essentials + Advanced, session presets — CR-0013), subentry crew → agent → instructions flow + reconfigure (CR-0003) | P0 |
| `sensor.py` | `test_sensor.py` | Bridge status/agent count state + attributes (tool_surface/read_only_safe), per-agent tokens + cost sensors (CR-0009): totals summing, None on missing/non-numeric data (BG0006), device attachment | P1 |
| `binary_sensor.py` | `test_binary_sensor.py` | Connected state, device class | P1 |
| `event.py` | `test_event.py` | Event entity firing on message received, event data shape | P1 |
| `services.py` | `test_services.py`, `test_broadcast.py` | Input validation, agent_id lookup + default-agent fallback, `ServiceValidationError` semantics (CR-0016), bridge client call, response formatting, broadcast responses-object normalisation, ask_with_image attachment shape, announce availability gating, memory record/recall (CR-0010) | P1 |
| `webhook.py` | `test_webhook.py` | Persistent webhook id reuse, local-only/POST-only registration, stale-handler replacement, stale-subscription cleanup, bridge registration fallback, event dispatch (health push, roster refresh, bridge:upgraded), invalid-payload 400 (BG0014) (CR-0014) | P0 |
| `drift.py` | `test_drift_surface.py` | Agent-context drift check (version baseline, deprecations, issue raise/clear), fleet-doctor verdict → opt-in repair issue (CRITICAL only, toggle-off clears — CR-0012/BG0011) | P1 |
| `diagnostics.py` | `test_diagnostics.py` | Redaction of token (and legacy caller_id), doctor/usage/agents payload shape (CR-0009) | P1 |
| `ai_task.py` | `test_ai_task.py` | Code-fence stripping, structured JSON parse + error path, plain-text generate_data (US0039) | P1 |
| `helpers.py` | `test_helpers.py` | Recursive text extraction (priority keys, depth limit, BG0013 fail-soft), caller-id resolution (BG0004), agent selectability/crew/label helpers (CR-0003/BG0005) | P1 |

### Integration Testing

| Attribute | Value |
|-----------|-------|
| Scope | Config flow round-trips, coordinator + entity updates, service calls |
| Framework | pytest + pytest-homeassistant-custom-component |
| Execution | `python -m pytest tests/ -v` (runs with unit tests) |

**Integration test scenarios:**

| Scenario | What it covers |
|----------|---------------|
| Config flow happy path | Enter URL + token (+ SSL toggle) → bridge responds healthy → crew-labelled agent picker → select default → entry created |
| Config flow auth failure | Enter URL + token → bridge returns 401 → show auth error → do not create entry |
| Config flow unreachable | Enter URL → connection refused → show connectivity error |
| Config flow self-signed bridge | ssl_verify unticked first-run → client created with verification off → onboarding succeeds (CR-0016) |
| Subentry flow | Crew picker → crew-scoped agent picker → instructions default → subentry created; reconfigure edits instructions (CR-0003) |
| Options flow agent change | Change default agent → entry data updated → integration reloads → conversation routes to new agent |
| Options flow session preset | Session-continuity dropdown value stored as int; legacy non-preset value falls back to default (CR-0013) |
| Coordinator poll cycle | Setup entry → coordinator polls → sensors update → binary sensor connected |
| Coordinator bridge down | Setup entry → bridge goes offline → 3 polls fail → sensors show offline → bridge returns → sensors recover |
| Coordinator observability refresh | Discovery cycle → usage fetched per agent + doctor fetched; one agent's failure keeps its last-known value; outage carries usage/doctor forward (CR-0009/BG0007) |
| Webhook push valid status | `{"status": "degraded"}` push → bridge_status updated without a poll |
| Webhook push invalid status | Non-string / unknown-vocabulary status push → ignored (CR-0014) |
| Webhook push agent health | `{"agentId": "cora", "healthy": false}` → agent flag + healthy count updated; malformed types ignored; unknown agent triggers a refresh (CR-0014) |
| Webhook persistent id | Second setup reuses the persisted webhook id; stale bridge subscription cleaned up first (CR-0014) |
| Conversation round-trip | User sends message → entity builds layered prompt → calls bridge → reply in ChatLog → fires message + audit events |
| Conversation with room | Voice request from device in "Kitchen" area → source block carries the area (and floor) |
| Conversation with satellite_id | Voice request with satellite_id different from device_id → area resolved from the satellite's device entry |
| Conversation caller context | Voice request → chat request includes `caller_context` (source_type voice, device, area, account unverified, local time) |
| Conversation text input | Text input (no device_id) → `caller_context.source_type: "text"`; automation-parented turns classified "automation" |
| Conversation extra_system_prompt | Pipeline provides extra_system_prompt → included as the final prompt layer |
| Conversation language passthrough | Voice input with language "de" → IntentResponse.language set to "de" |
| Session channel reuse | Two turns from the same device within the idle window → same `ha:{agent}:{scope}:{epoch}` channel (US0032) |
| Session channel rotation | Turn after the idle gap (or a backwards clock jump) → epoch increments → new bridge session (US0032) |
| Safety caution folded | Exposed entities include a lock → system prompt carries the deny/confirm caution (US0027) |
| Confirm marker (non-streaming) | Reply prefixed `[confirm:high]` → marker stripped, severity on events, conversation kept open (US0036) |
| Confirm marker (streaming) | Marker split across the first deltas → stripped before any content reaches TTS/ChatLog; severity surfaced (BG0012) |
| Streaming fallback | Stream fails / yields nothing → non-streaming path runs without double-appending the assistant turn (US0033) |
| Actuation audit event | Every reactive turn fires `agent_bridge_actuation_audit` with source, area, risky domains, confirmation state (US0027/AC3) |
| Response nested extraction | Bridge returns deeply nested response structure → text extracted via priority key traversal |
| Auth failure handling | Bridge returns 401 → BridgeAuthError raised; 403 with a caller-identity code → BridgeCallerError (BG0004) |
| Client uses HA session | Client initialised → uses async_get_clientsession() not new aiohttp.ClientSession |
| Client path encoding | Agent id with `/` or spaces → URL-encoded in usage/memory/webhook paths (CR-0015) |
| Conversation bridge error | Bridge returns AGENT_TIMEOUT → conversation returns user-friendly error message |
| Service send_message | Automation calls send_message → bridge receives correct request → response returned |
| Service default-agent fallback | send_message / ask_with_image without agent_id → configured default agent used (CR-0016) |
| Service invoke_tool | Automation calls invoke_tool → bridge receives the v4.36 `agent`/`tool` body → response returned |
| Service invalid agent | Service called with unknown agent_id → `ServiceValidationError` (CR-0016) |
| Service ask_with_image | Camera snapshot base64-encoded into the bridge attachment shape; capture failure returns a clean error (US0035) |
| Service announce | Unavailable satellite skipped unless priority critical; assist_satellite.announce called otherwise (US0037) |
| Service memory record/recall | memory_record posts content (+tags); memory_recall returns the items list; default-agent fallback; bridge errors in the response (CR-0010) |
| Voice-capability gating | Orchestrators / chatbots / workerbots / model passthroughs get no conversation or ai_task entity (US0028/CR-0003) |
| Usage sensors | Tokens sensor sums totalIn+totalOut; cost sensor None without pricing; null fields never raise (CR-0009/BG0006) |
| Fleet-doctor repair | CRITICAL verdict + doctor_alerts on → repair issue raised; WARNING → none; toggle off clears (CR-0012/BG0011) |
| Drift repair | agent-context version past `TESTED_BRIDGE_VERSION` or deprecations reported → repair issue raised; clears on recovery (US0029) |
| Diagnostics download | Token (and legacy caller_id) redacted; doctor/usage/agents present (CR-0009) |
| AI task structured data | Structure requested → JSON-only instruction appended → fenced JSON parsed; invalid JSON raises HomeAssistantError (US0039) |
| OpenAPI contract | Every consumed (method, path) pair exists in the captured bridge spec fixture (CR-0008) |
| Entity exposure cap | Expose 300 entities → context contains at most 250 |
| Entity exposure attributes | Expose light at 75% brightness → context includes "brightness: 75" |
| Continuation detection question | Agent response ends with "?" + continuation phrase → continue_conversation=True |
| Continuation detection statement | Agent response ends with "." → continue_conversation=False |
| Broadcast service | Automation calls broadcast → POST /v1/broadcast with `messages[]` + tags (default `['operator']`) → responses object normalised to a list |
| Broadcast with tags | Automation calls broadcast with tags filter → bridge receives tags in request body |
| Template entity exposure | Expose template sensor (binary_sensor.house_occupied) and group (group.kitchen_lights) → both appear in entity context without filtering |
| Unload entry | Remove integration → webhook unregistered (bridge + HA) → services removed with the last entry → entities removed |

### Approach: usage / doctor / memory / diagnostics / contract suites (CR-0009/CR-0010)

All of these mock the bridge — **never** a live bridge, per the TDD rule:

- **Usage & cost** (`test_sensor.py`, `test_coordinator.py`): canned
  `/v1/agents/{id}/usage` payloads (full, partial, null-fielded, missing) drive the
  sensors; regression pins for BG0006 (None, not 0/raise) and BG0007/BG0008
  (carry-forward + defensive copies).
- **Fleet doctor** (`test_drift_surface.py`): canned `/v1/doctor` verdicts exercise
  the repair-issue state machine — CRITICAL raises, WARNING stays advisory (BG0011),
  the CR-0012 opt-in gate, and issue-registry churn suppression (BG0007).
- **Memory** (`test_services.py`): mocked client asserts the record/recall bodies,
  `?q=` pass-through, default-agent fallback, and error envelopes (CR-0010).
- **Diagnostics** (`test_diagnostics.py`): a mocked coordinator verifies the payload
  shape and redaction set.
- **Contract** (`test_openapi_contract.py`): the consumed (method, path) list is
  checked against `tests/fixtures/bridge_openapi_contract.json`, a captured slice of
  the live `GET /v1/openapi.json`; refresh the fixture when the bridge baseline
  moves, and a consumed endpoint disappearing fails in CI instead of at runtime.
- **CR-0014 webhook regressions** (`test_webhook.py`, `test_coordinator.py`):
  persistent-id reuse, stale-subscription cleanup, local-only/POST-only registration
  flags, and push validation (status whitelist, typed agentId/healthy, non-object
  payload → 400 per BG0014).
- **BG0012 streaming regression** (`test_streaming.py`): the delta adapter is fed
  confirm markers split across chunk boundaries, marker-only streams, and
  non-marker text to prove nothing marker-shaped leaks to TTS/ChatLog and severity
  is reported.

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
| Usage & cost sensors | Dashboard: verify tokens + estimated-cost sensors track bridge usage | Not Started |
| send_message service | Automation: send message to Cora → verify response | Not Started |
| invoke_tool service | Automation: invoke tool on agent → verify response | Not Started |
| Memory services | Automation: memory_record a fact → memory_recall returns it | Not Started |
| Event: message received | Automation: trigger on message_received event → verify fires | Not Started |
| Event: actuation audit | Automation: trigger on agent_bridge_actuation_audit → verify fires per reactive turn | Not Started |
| Options flow | Change default agent → verify conversation routes to new agent | Not Started |
| Graceful degradation | Bridge offline → voice command → user hears "Bridge is offline" | Not Started |
| Multi-turn voice | Agent asks follow-up question → verify HA keeps listening | Not Started |
| Session continuity | Two voice commands within the idle window → agent has prior context; after the gap → fresh session | Not Started |
| Voice response format | Voice command → agent response is concise, no markdown (audio-only modality effect) | Not Started |
| Room-specific command | "Turn on the lights" from kitchen satellite → kitchen lights turn on, not all | Not Started |
| Actuation (light) | "Turn on the kitchen lights" → agent actuates via its /api/mcp mount → light.kitchen turns on → agent confirms from live state | Not Started |
| Actuation (climate, confirm) | "Set heating to 21" → agent asks a [confirm:*] question → user confirms → thermostat changes | Not Started |
| Actuation (multi) | "Turn off everything in the study" → agent actuates multiple entities via its mount | Not Started |
| Unexposed entity blocked | Agent asked about an unexposed entity → not in the grounding hint → agent reports it cannot | Not Started |
| Fleet-doctor repair | doctor_alerts on + broken fleet → HA repair issue appears; recovers → clears | Not Started |
| Diagnostics download | Download diagnostics → token redacted, doctor/usage present | Not Started |
| AI task | ai_task.generate_data with a structure → valid JSON data returned | Not Started |
| Streaming voice | enable_streaming on → TTS starts before the full reply completes | Not Started |
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
| Bridge API | Mocked `BridgeClient` (AsyncMock) / mocked aiohttp session | Return canned health, discovery, chat, usage, doctor, memory responses; assert request bodies |
| SSE stream | Mocked `aiohttp` response `.content` line iterator | Feed v4.36 `event:message`/`event:done` frames (and legacy deltas) to the client parser |
| HA entity registry | pytest-homeassistant-custom-component fixtures | Provide mock entities for exposure testing |
| HA device registry | pytest-homeassistant-custom-component fixtures | Provide mock device-to-area mappings |
| HA area registry | pytest-homeassistant-custom-component fixtures | Provide mock area names |
| HA conversation API | Real `ChatLog` + mock `ConversationInput` | Exercise `_async_handle_message` with voice/text/automation turns |
| HA service registry | Mock hass.services.async_call | Verify the announce service's assist_satellite call without real devices |
| HA issue registry | Patched `issue_registry` helpers | Verify drift + fleet-doctor repair issues raise/clear (US0029/CR-0012) |
| HA webhook component | Patched `webhook.async_register`/`async_unregister` | Verify persistent-id registration flags and lifecycle (CR-0014) |

### Test Fixtures

| Type | Location | Purpose |
|------|----------|---------|
| Bridge OpenAPI contract | `tests/fixtures/bridge_openapi_contract.json` | Captured slice of `GET /v1/openapi.json` for the consumed-endpoint contract test (CR-0008) |
| Bridge responses (health, discovery, chat, usage, doctor, memory, errors) | Inline dicts in each test module | Canned payloads pinned to the v4.36+ shapes (US0022/US0023) |
| Config entry data | `tests/conftest.py` + per-module helpers | Standard config entry / hass fixtures |

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
| Unit | pytest + pytest-asyncio | Python |
| Integration | pytest + pytest-homeassistant-custom-component | Python |
| E2E | curl scripts + manual | Bash |
| Coverage | pytest-cov (coverage.py, local — no CI gate) | N/A |
| Mocking | unittest.mock (MagicMock/AsyncMock) | Python |

---

## CI/CD Integration

### Pipeline Stages

1. **Pre-commit (local):** ruff lint + format check, mypy type check
2. **PR / push (`.github/workflows/validate.yml`):** ruff lint + format check; full pytest suite against pinned HA `2026.2.3` on Python 3.13 (keep `HA_VERSION` in step with `const.TESTED_HA_VERSION` — Critical Rule 9); hassfest + HACS validation
3. **Merge to main:** Full test suite
4. **Release:** Pre-release gate (`reconcile --verify` + four-pillar review) → tag → HACS picks up new version

### Quality Gates

| Gate | Criteria | Blocking |
|------|----------|----------|
| ruff lint + format | Zero errors (CI) | Yes |
| mypy type check | Zero errors (local) | Yes |
| pytest suite | 100% pass on pinned HA/py (CI) | Yes |
| hassfest / HACS validation | Pass (CI) | Yes |
| Unit coverage | >= 90% target (measured locally with pytest-cov; not a CI gate) | No (advisory) |
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
  __init__.py                      # Package marker
  conftest.py                      # Shared fixtures: config entries, mock bridge, mock entities
  fixtures/
    bridge_openapi_contract.json   # Captured bridge OpenAPI slice (CR-0008)
  test_agent_selection.py          # Selectability filtering, crew picker, instructions (CR-0003)
  test_ai_task.py                  # AI Task platform (US0039)
  test_binary_sensor.py            # Binary sensor state
  test_broadcast.py                # Broadcast service + responses-object normalisation
  test_client.py                   # Bridge client HTTP tests (incl. usage/doctor/memory, CR-0015 encoding)
  test_config_flow.py              # Config flow + options flow (+ first-run SSL toggle, CR-0016)
  test_conversation.py             # Prompt building, caller context, sessions, confirm markers
  test_conversation_integration.py # ConversationEntity via _async_handle_message + real ChatLog
  test_coordinator.py              # Polling, caching, degradation, webhook pushes (CR-0014)
  test_diagnostics.py              # Diagnostics platform + redaction (CR-0009)
  test_drift_surface.py            # v4.x discovery/health surface, drift + doctor repairs (US0028/US0029)
  test_event.py                    # Event entity firing
  test_exposure.py                 # Entity exposure formatting + recent changes
  test_helpers.py                  # Text extraction, caller id, crew/label helpers
  test_openapi_contract.py         # Consumed-endpoint contract vs the captured spec (CR-0008)
  test_sensor.py                   # Bridge + per-agent usage/cost sensor state (CR-0009)
  test_services.py                 # Service handlers (incl. memory, ask_with_image, announce)
  test_streaming.py                # SSE parsing, delta adapter, confirm-marker strip (BG0012)
  test_webhook.py                  # Webhook lifecycle + hardening (CR-0014)
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
| 2026-06-09 | Claude | RV0006 release-gate review: currency note (top) — tool-execution test objective + `test_tool_executor.py`/`test_init.py` removed (CR-0006); new `test_diagnostics`/`test_openapi_contract` + extended suites for CR-0008..0010 + BG0005. Full test-tree/module-table reconcile tracked in CR-0011. |
| 2026-07-04 | Claude | CR-0011 full reconcile: test tree + module table now match `tests/` exactly (19 test modules + the OpenAPI contract fixture); tool-execution objective and scenarios removed; objectives + integration scenarios rewritten to the shipped design (Option A actuation, caller_context, idle-window sessions, confirm markers); documented the usage/doctor/memory/diagnostics/contract test approach and the CR-0014 (webhook hardening) + BG0012 (streaming confirm strip) regression suites; test doubles/fixtures/CI gates re-baselined to the real tooling (unittest.mock, pinned HA 2026.2.3 / py3.13). |
