# US0008: Tool Executor

> **Status:** Done
> **Epic:** [EP0002: Conversation & Home Control](../epics/EP0002-conversation-and-control.md)
> **Owner:** Darren Benson
> **Created:** 2026-04-05

## User Story

**As a** bridge agent
**I want** my tool_call responses executed as real HA service calls
**So that** I can actually control the home, not just describe what I would do

## Context

The tool executor is the critical path that turns agent intent into real-world action. When an agent responds with tool_calls (OpenAI format), the executor validates the target entity against the exposure list, calls `hass.services.async_call()`, and returns structured results back to the agent. Supports both single (`execute_service`) and batch (`execute_services`) calls, with a 10-iteration loop cap (ADR-005) to prevent runaway agents. All behaviour gated behind the `enable_tool_calls` config option.

---

## Acceptance Criteria

### AC1: Single service execution
- **Given** a tool_call with name "execute_service" and arguments containing domain, service, and entity_id
- **When** the tool executor processes it
- **Then** it calls `hass.services.async_call(domain, service, target={"entity_id": entity_id})` and returns a success result

### AC2: Batch service execution
- **Given** a tool_call with name "execute_services" and arguments containing a list of service calls
- **When** the tool executor processes it
- **Then** all calls execute in parallel via `asyncio.gather(return_exceptions=True)` and per-entity results are returned

### AC3: Entity validation against exposure list
- **Given** a tool_call targeting an entity_id
- **When** the entity_id is not in the current exposure list
- **Then** execution is refused and an error result is returned: `{"success": false, "error": "Entity <id> not found in exposed entities"}`

### AC4: 10-iteration loop cap
- **Given** an agent that keeps returning tool_calls
- **When** 10 iterations of the tool call loop have been reached
- **Then** the loop terminates and returns a user-friendly error: "Agent could not complete the request"

### AC5: Content + tool_calls handling
- **Given** an agent response containing both content and tool_calls
- **When** the tool executor processes it
- **Then** tool_calls are executed first, content is preserved in the message history, and the agent is given a chance to provide a final response grounded in actual tool outcomes

### AC6: Error results as JSON
- **Given** a tool call that fails (entity not found, service timeout, invalid domain)
- **When** the failure occurs
- **Then** a JSON error result is returned to the agent, not a Python exception: `{"success": false, "error": "<descriptive message>"}`

### AC7: Success results as JSON
- **Given** a tool call that succeeds
- **When** the service call completes
- **Then** a JSON success result is returned: `{"success": true, "entity_id": "<id>", "service": "<domain>.<service>"}`

### AC8: Tool execution timeout
- **Given** a service call in progress
- **When** 10 seconds elapse without completion
- **Then** the call times out and returns: `{"success": false, "error": "Service call timed out after 10s"}`

### AC9: Gated behind enable_tool_calls
- **Given** enable_tool_calls is False in config
- **When** an agent response contains tool_calls
- **Then** tool_calls are ignored and the agent's content (if any) is returned directly; if no content, a message explains that tool execution is disabled

### AC10: Tool invoked event
- **Given** a tool call is executed (success or failure)
- **When** execution completes
- **Then** an agent_bridge_tool_invoked event fires with agent_id, tool_name, status (success/failure), and duration_ms

### AC11: Domain and service extraction
- **Given** tool_call arguments with domain and service fields
- **When** the executor processes the call
- **Then** domain and service are extracted correctly and passed to hass.services.async_call

### AC12: Additional service data
- **Given** tool_call arguments containing extra fields beyond domain, service, entity_id (e.g. brightness, temperature)
- **When** the executor processes the call
- **Then** extra fields are passed as service_data to hass.services.async_call

---

## Scope

### In Scope
- `custom_components/agent_bridge/tool_executor.py`
- `execute_service()` -- single service call with validation
- `execute_services()` -- batch parallel execution with per-entity results
- Entity validation against exposure list
- Tool call loop (in conversation.py, driven by tool_executor) with 10-iteration cap
- Timeout handling (10s per call)
- JSON result formatting (success and error)
- Event firing per execution
- Gate check for enable_tool_calls

### Out of Scope
- Bridge communication (US0002 -- tool results sent back via BridgeClient.chat)
- Entity exposure building (US0006 -- provides the validation set)
- Conversation flow orchestration (US0007 -- calls tool executor)

---

## Technical Notes

The tool executor is called by the conversation agent (US0007) within the tool call loop. The loop lives in conversation.py but the execution logic lives in tool_executor.py. Use `asyncio.wait_for()` with DEFAULT_TOOL_TIMEOUT (10s) for individual call timeouts. For batch execution, wrap each call in its own timeout before gathering. The exposure list (set of entity_ids) is passed in from US0006 -- do not rebuild it in the executor. Service data extraction: pop domain, service, entity_id from arguments dict; remaining keys become service_data.

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| tool_call with unknown function name (not execute_service/execute_services) | Return error result: "Unknown tool: <name>" |
| tool_call with malformed arguments (not valid JSON) | Return error result: "Invalid tool arguments" |
| tool_call with missing required fields (no domain or service) | Return error result: "Missing required field: <field>" |
| Domain does not exist in HA | Return error result: "Domain '<domain>' not found" |
| Service does not exist for domain | Return error result: "Service '<domain>.<service>' not found" |
| Batch with mix of valid and invalid entities | Execute valid ones, return per-entity results (partial success) |
| Agent returns empty tool_calls array | Treat as no tool_calls, proceed to final response |
| Agent returns tool_calls after loop cap reached | Return error to user, do not execute |
| Concurrent tool calls targeting same entity | Allow (HA handles service call ordering) |
| enable_tool_calls toggled during conversation | Check gate at execution time, not at conversation start |

---

## Test Scenarios

- [ ] execute_service calls hass.services.async_call with correct domain, service, entity_id
- [ ] execute_service passes extra fields as service_data (e.g. brightness)
- [ ] execute_service returns success JSON on completion
- [ ] execute_service returns error JSON when entity not in exposure list
- [ ] execute_service returns error JSON on timeout (10s)
- [ ] execute_service returns error JSON for invalid domain
- [ ] execute_service returns error JSON for invalid service
- [ ] execute_services runs multiple calls in parallel
- [ ] execute_services returns per-entity results
- [ ] execute_services handles partial failure (some succeed, some fail)
- [ ] Loop cap: 10th iteration terminates with error message
- [ ] Loop cap: 9th iteration with tool_calls proceeds normally
- [ ] Content + tool_calls: tools executed, content preserved in history
- [ ] Content + tool_calls: final response from last content-only reply
- [ ] enable_tool_calls=False: tool_calls ignored, content returned
- [ ] enable_tool_calls=False, no content: explanation message returned
- [ ] agent_bridge_tool_invoked event fired on success
- [ ] agent_bridge_tool_invoked event fired on failure
- [ ] Event contains agent_id, tool_name, status, duration_ms
- [ ] Unknown function name returns descriptive error
- [ ] Malformed arguments return descriptive error
- [ ] Missing required fields return descriptive error
- [ ] Empty tool_calls array treated as no tool_calls

---

## Dependencies

### Story Dependencies

| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| [US0001](US0001-project-scaffold.md) | Hard | const.py (EVENT_TOOL_INVOKED, DEFAULT_TOOL_TIMEOUT, CONF_ENABLE_TOOL_CALLS) | Done |
| [US0006](US0006-entity-exposure.md) | Hard | Exposure list (set of entity_ids) for validation | Done |
| [US0007](US0007-conversation-agent-core.md) | Hard | Conversation agent provides the tool call loop context | Done |

### External Dependencies

| Dependency | Type | Status |
|------------|------|--------|
| Home Assistant Core 2025.1.0+ | Framework | Available |
| HA Service Registry (hass.services.async_call) | Internal API | Available |

---

## Estimation

**Story Points:** 5
**Complexity:** High

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-04-05 | Claude | Initial story generation |
