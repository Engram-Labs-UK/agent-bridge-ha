# EP0002: Conversation & Home Control

> **Status:** Done
> **Owner:** Darren Benson
> **Reviewer:** --
> **Created:** 2026-04-05
> **Target Release:** 0.1.0

## Summary

The core value path: register a conversation agent with HA Assist, build AI-consumable entity context, inject room awareness, execute tool_calls as HA service calls, and persist sessions across restarts. After this epic, users can control their home via voice through the bridge.

## Inherited Constraints

| Source | Type | Constraint | Impact |
|--------|------|------------|--------|
| PRD | Performance | Entity context build < 500ms for 250 entities | Exposure must be efficient |
| PRD | Security | Only exposed entities targetable by tool_calls | Tool executor validates against exposure list |
| TRD | Architecture | Tool call loop capped at 10 iterations (ADR-005) | Prevents infinite agent loops |
| TRD | Architecture | Batch tool_calls via asyncio.gather (ADR-005) | Parallel execution with per-entity results |

---

## Business Context

### Problem Statement
Voice satellite users cannot interact with AI agents through HA Assist. There is no way to expose HA entity state to agents or have agents control devices via voice commands.

**PRD Reference:** [Primary Conversation Agent](../prd.md#primary-conversation-agent)

### Value Proposition
This is the "wow" feature -- voice commands processed by intelligent agents that understand the home and can actually control it. Transforms the homelab from manual control to conversational AI control.

### Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Voice command success rate | 0% (not possible) | > 90% for exposed entities | E2E testing |
| Entity context build time | N/A | < 500ms for 250 entities | Timed in test (blocking gate) |
| Tool call execution | Not possible | < bridge response + 200ms | Timed end-to-end |

---

## Scope

### In Scope
- Conversation agent (`conversation.py`): HA Assist registration, system prompt building (room + entities + extra), agent routing, voice source signalling, language passthrough, continuation detection
- Entity exposure (`exposure.py`): format HA entities with areas/attributes, 250-entity cap, truncation strategy
- Tool executor (`tool_executor.py`): execute HA services from tool_calls, entity validation, batch execution, loop cap, error/success result formatting
- Session manager (in `__init__.py`): agent-scoped session IDs, HA Store persistence, load on startup

### Out of Scope
- Per-agent conversation agents (EP0004) -- this epic creates only the primary/default agent
- SSE streaming (EP0006)
- Sensor/event entities (EP0003)
- Webhook-based health updates (EP0005)

### Affected Personas
- **Voice satellite users:** Can now talk to agents via Assist
- **Darren (operator):** Configures which agent handles voice/chat
- **Agent Bridge agents:** Receive entity context, can control the home

---

## Acceptance Criteria (Epic Level)

- [x] Conversation agent selectable in HA Assist pipeline settings
- [x] System prompt includes entity context, room awareness, and optional extra_system_prompt
- [x] Voice requests tagged with `source: "voice"` and device/area metadata
- [x] Agent tool_calls execute HA services with entity validation
- [x] Tool call loop capped at 10 iterations with clear error on exceeded
- [x] Batch tool_calls (execute_services) run in parallel with per-entity results
- [x] Failed tool calls return descriptive JSON error to agent (not exception)
- [x] Session IDs persist across HA restarts via HA Store
- [x] Continuation detection triggers on question patterns, suppresses on exclusion phrases
- [x] Entity context builds in < 500ms for 250 entities
- [x] ruff lint, ruff format, and mypy pass with zero errors

---

## Dependencies

### Blocked By

| Dependency | Type | Status | Owner |
|------------|------|--------|-------|
| EP0001 | Epic | Done | Darren Benson |

### Blocking

| Item | Type | Impact |
|------|------|--------|
| EP0003 | Epic | Events need conversation agent to fire message/tool events |
| EP0004 | Epic | Per-agent entities extend conversation agent pattern |
| EP0006 | Epic | Streaming and continuation build on conversation agent |

---

## Risks & Assumptions

### Assumptions
- HA's `conversation.async_set_agent()` API is stable in 2025.1.0+
- Bridge agents return tool_calls in standard OpenAI format
- HA's entity expose settings are accessible via `async_should_expose()`

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Agent returns malformed tool_calls | Medium | Medium | Validate tool_call structure before execution, return error to agent |
| Entity exposure too slow for large homes | Low | High | Profile and optimise; 250 cap provides hard limit |
| Session ID collisions | Very Low | Medium | UUID-based random hex in session format |

---

## Technical Considerations

### Architecture Impact
Establishes the conversation agent pattern. All subsequent conversation-related features (per-agent, streaming, continuation) extend this foundation.

### Integration Points
- HA Conversation API (`AbstractConversationAgent`)
- HA Entity/Device/Area registries (for exposure and room awareness)
- HA Service registry (`hass.services.async_call`) for tool execution
- HA Store for session persistence
- Bridge Client (from EP0001) for chat completions

---

## Sizing

**Story Points:** 21
**Estimated Story Count:** 6

**Complexity Factors:**
- Tool execution loop with multiple ADR-005 rules (most complex module)
- Entity exposure format must match what agents expect
- Three-layer system prompt (room + entities + extra)
- Session persistence with HA Store
- Continuation detection with configurable phrase lists

---

## Story Breakdown

| | ID | Title | Status | Points |
|---|-----|-------|--------|--------|
| [x] | [US0006](../stories/US0006-entity-exposure.md) | Entity Exposure | Done | 3 |
| [x] | [US0007](../stories/US0007-conversation-agent-core.md) | Conversation Agent Core | Done | 5 |
| [x] | [US0008](../stories/US0008-tool-executor.md) | Tool Executor | Done | 5 |
| [x] | [US0009](../stories/US0009-session-persistence.md) | Session Persistence | Done | 2 |
| [x] | [US0010](../stories/US0010-continuation-detection.md) | Continuation Detection | Done | 2 |

**Total:** 5 stories, 17 points

---

## Open Questions

None -- tool execution rules defined in TRD ADR-005, entity exposure decided in TRD Q2.

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-04-05 | Claude | Initial epic generation from PRD |
