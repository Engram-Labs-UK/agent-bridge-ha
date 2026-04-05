# US0014: Services & Voice Debug Logging

> **Status:** Done
> **Epic:** [EP0003: Observability & Automation](../epics/EP0003-observability-and-automation.md)
> **Owner:** Darren Benson
> **Created:** 2026-04-05

## User Story

**As a** home automation operator
**I want** HA services for sending messages and invoking tools, plus voice debug logging
**So that** I can interact with agents from scripts and automations, and troubleshoot voice pipeline routing

## Context

Two HA services (`agent_bridge.send_message` and `agent_bridge.invoke_tool`) expose agent interaction for use in scripts, automations, and the developer tools panel. Both return response data via `response_variable`. Voice debug logging adds conditional info-level log lines when `debug_logging` is enabled in the config entry, capturing routing decisions without exposing sensitive data.

---

## Acceptance Criteria

### AC1: send_message service
- **Given** the integration is loaded
- **When** `agent_bridge.send_message` is called with `message` (required)
- **Then** the bridge client sends the message to the bridge API and the service returns the agent's response text via `response_variable`

### AC2: send_message optional parameters
- **Given** `agent_bridge.send_message` is called
- **When** `agent_id` (optional) and/or `session_id` (optional) are provided
- **Then** the bridge client includes them in the API request

### AC3: invoke_tool service
- **Given** the integration is loaded
- **When** `agent_bridge.invoke_tool` is called with `agent_id` (required) and `tool_name` (required)
- **Then** the tool is invoked via the bridge client and the service returns the tool result via `response_variable`

### AC4: invoke_tool optional args
- **Given** `agent_bridge.invoke_tool` is called
- **When** `args` (optional, object) is provided
- **Then** the args are passed to the tool invocation

### AC5: Agent ID validation
- **Given** either service is called with an `agent_id`
- **When** the agent_id does not match any agent in the coordinator's cached agent list
- **Then** the service raises a `ServiceValidationError` with a descriptive message

### AC6: Services return response data
- **Given** either service is called from an automation with `response_variable`
- **When** the bridge returns a response
- **Then** the response data (text, agent_id, model) is available in the response variable

### AC7: Service definitions
- **Given** `services.yaml` exists
- **When** HA loads the integration
- **Then** both services appear in Developer Tools > Services with field descriptions and correct required/optional markers

### AC8: Voice debug logging -- enabled
- **Given** `debug_logging` is enabled in the config entry
- **When** a voice conversation is processed
- **Then** the integration logs at INFO level: agent name, session ID, area, device_id, satellite_id

### AC9: Voice debug logging -- disabled
- **Given** `debug_logging` is disabled (default)
- **When** a voice conversation is processed
- **Then** no debug log lines are emitted at INFO level

### AC10: Sensitive data exclusion
- **Given** debug logging is enabled
- **When** a conversation is logged
- **Then** the log never contains the API token or the full prompt/system message content

---

## Scope

### In Scope
- `custom_components/agent_bridge/services.py` -- service handler functions
- `custom_components/agent_bridge/services.yaml` -- service definitions
- Voice debug logging logic (in conversation agent or shared helper)
- Agent ID validation against coordinator cache

### Out of Scope
- Bridge client implementation (US0002)
- Coordinator implementation (US0005)
- Broadcast service (EP0005)

---

## Technical Notes

Services are registered via `hass.services.async_register` in `async_setup_entry` or a dedicated `async_setup_services` helper. Service schemas use `vol.Schema` with `vol.Required` and `vol.Optional`. The `response_variable` pattern requires `SupportsResponse.OPTIONAL` in the service registration. Agent ID validation should fetch the agent list from `coordinator.data.agents` and check membership. Voice debug logging should use `_LOGGER.info(...)` gated behind a check of `entry.data.get(CONF_DEBUG_LOGGING, False)`. Never log `entry.data[CONF_TOKEN]`.

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| send_message with no agent_id | Bridge uses its default agent routing |
| invoke_tool with unknown tool_name | Bridge returns error; service returns error in response data |
| Agent ID valid at validation time but agent goes down before request | Bridge handles failover; service returns bridge's error response |
| Bridge unreachable during service call | Service raises `HomeAssistantError` with descriptive message |
| Empty message string | Service raises `ServiceValidationError` (message is required, non-empty) |
| args is not a valid JSON object | Voluptuous schema validation rejects the call |
| debug_logging toggled at runtime via options flow | Next conversation uses the updated setting |
| Concurrent service calls | Each call is independent; no shared mutable state |

---

## Test Scenarios

- [ ] send_message with message only sends to bridge default agent
- [ ] send_message with agent_id routes to specified agent
- [ ] send_message with session_id includes session in request
- [ ] send_message returns response text via response_variable
- [ ] invoke_tool with agent_id and tool_name invokes correctly
- [ ] invoke_tool with args passes arguments to bridge
- [ ] invoke_tool returns tool result via response_variable
- [ ] Invalid agent_id raises ServiceValidationError
- [ ] Bridge unreachable raises HomeAssistantError
- [ ] services.yaml defines both services with correct fields
- [ ] Debug logging emits INFO log with agent, session, area, device_id, satellite_id when enabled
- [ ] Debug logging emits nothing when disabled
- [ ] Token never appears in debug log output
- [ ] Full prompt/system message never appears in debug log output
- [ ] Empty message rejected by schema validation

---

## Dependencies

### Story Dependencies
| Story | Relationship |
|-------|-------------|
| [US0002](US0002-bridge-client.md) | Bridge client sends messages and invokes tools |
| [US0005](US0005-coordinator-and-setup.md) | Coordinator provides cached agent list for validation |

### External Dependencies
| Dependency | Type | Status |
|------------|------|--------|
| Home Assistant Core 2025.1.0+ | Framework | Available |

---

## Estimation

**Story Points:** 3
**Complexity:** Medium

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-04-05 | Claude | Initial story generation |
