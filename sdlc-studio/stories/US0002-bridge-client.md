# US0002: Bridge Client

> **Status:** Done
> **Epic:** [EP0001: Bridge Foundation](../epics/EP0001-bridge-foundation.md)
> **Owner:** Darren Benson
> **Created:** 2026-04-05

## User Story

**As the** integration
**I want** an async HTTP client that speaks the Agent Bridge REST API
**So that** all bridge communication goes through a single, well-tested client

## Context

The bridge client is the only module that makes HTTP calls. Every other module that needs bridge data goes through this client. Uses HA's shared aiohttp session.

---

## Acceptance Criteria

### AC1: Client initialisation
- **Given** a bridge URL, token, and HA aiohttp session
- **When** BridgeClient is created
- **Then** it stores the base URL, sets Authorization: Bearer header, and uses the provided session (never creates its own)

### AC2: Discovery endpoint
- **Given** a healthy bridge
- **When** discover() is called
- **Then** it calls GET /v1/discovery with auth header and returns list[AgentInfo]

### AC3: Health endpoint
- **Given** a healthy bridge
- **When** health(depth="shallow") is called
- **Then** it calls GET /health?depth=shallow and returns typed health data with status, version, uptime, agent counts

### AC4: Chat endpoint
- **Given** a bridge with a healthy agent
- **When** chat(messages, agent, channel, metadata) is called
- **Then** it calls POST /v1/chat/completions with correct body per TRD Section 5 and returns response with text content and optional tool_calls

### AC5: Tool invocation
- **Given** a bridge with a healthy agent
- **When** invoke_tool(agent_id, tool_name, args) is called
- **Then** it calls POST /v1/tools/invoke with correct body and returns result

### AC6: Connectivity check
- **Given** any bridge state
- **When** check_alive() is called
- **Then** it calls GET /health and returns True/False without raising exceptions

### AC7: Error handling
- **Given** a bridge that returns errors
- **When** connection refused → BridgeConnectionError raised
- **When** 401/403 response → BridgeAuthError raised
- **When** timeout → BridgeTimeoutError raised
- **When** bridge error JSON → appropriate typed exception with error code

### AC8: SSL configuration
- **Given** ssl_verify=False in config
- **When** any request is made
- **Then** SSL verification is disabled on the request

---

## Scope

### In Scope
- `custom_components/agent_bridge/client.py`
- Typed exception classes (BridgeConnectionError, BridgeAuthError, BridgeTimeoutError, BridgeError)
- All 5 client methods: discover, health, chat, invoke_tool, check_alive

### Out of Scope
- SSE streaming (EP0006)
- Broadcast (EP0005)
- Response text extraction (US0003)

---

## Technical Notes

Use HA's `async_get_clientsession(hass)` for the session. Exceptions should be a class hierarchy: BridgeError base, with Connection/Auth/Timeout as subclasses. The chat method must handle both text-only and tool_calls responses. Map bridge error codes (AGENT_TIMEOUT, AGENT_UNREACHABLE, etc.) to typed exceptions per TRD Section 5 error handling strategy.

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| Bridge returns non-JSON response | BridgeError with descriptive message |
| Bridge returns 500 | BridgeError with status code |
| Network timeout | BridgeTimeoutError after configured timeout |
| Bridge URL has trailing slash | Strip it to avoid double-slash in paths |
| Empty response body | BridgeError("Empty response from bridge") |
| Discovery returns empty agent list | Return empty list, no error |

---

## Test Scenarios

- [ ] discover() constructs correct URL and headers
- [ ] discover() parses agent list from response
- [ ] health(depth="shallow") returns typed health data
- [ ] health(depth="deep") returns per-agent health dict
- [ ] chat() constructs correct request body per TRD format
- [ ] chat() returns content from successful response
- [ ] chat() extracts tool_calls when present
- [ ] invoke_tool() constructs correct request body
- [ ] check_alive() returns True for healthy bridge
- [ ] check_alive() returns False for unreachable bridge (no exception)
- [ ] Connection refused raises BridgeConnectionError
- [ ] 401 response raises BridgeAuthError
- [ ] 403 response raises BridgeAuthError
- [ ] Timeout raises BridgeTimeoutError
- [ ] Bridge error JSON raises BridgeError with code
- [ ] SSL verification disabled when ssl_verify=False
- [ ] Client uses provided session, not new one
- [ ] Trailing slash in URL stripped

---

## Dependencies

### Story Dependencies

| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| [US0001](US0001-project-scaffold.md) | Hard | const.py for DOMAIN, CONF_* keys | Done |

---

## Estimation

**Story Points:** 5
**Complexity:** Medium

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-04-05 | Claude | Initial story generation |
