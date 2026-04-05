# US0019: Broadcast Service

> **Status:** Done
> **Epic:** [EP0005: Real-Time & Broadcast](../epics/EP0005-realtime-and-broadcast.md)
> **Owner:** Darren Benson
> **Created:** 2026-04-05

## User Story

**As an** automation builder
**I want** to send a message to all agents (or a tagged subset) in one service call
**So that** system-wide instructions don't need per-agent automations

## Acceptance Criteria

### AC1: Broadcast Service Registration
- **Given** the integration is loaded
- **When** services are registered
- **Then** `agent_bridge.broadcast` is available with fields: message (required), tags (optional list)

### AC2: Broadcast Execution
- **Given** a broadcast service call with a message
- **When** the service executes
- **Then** it calls `POST /v1/broadcast` on the bridge with the message and optional tags

### AC3: Aggregated Response
- **Given** a broadcast call completes
- **When** the bridge returns responses from multiple agents
- **Then** the service returns aggregated responses accessible via `response_variable`

### AC4: Partial Failure Handling
- **Given** a broadcast where one agent fails
- **When** other agents succeed
- **Then** individual failures are reported in the response without blocking successful ones

## Scope

### In Scope
- `broadcast()` method in BridgeClient
- `agent_bridge.broadcast` service handler in services.py
- Broadcast service schema in services.yaml
- Service strings in strings.json / translations/en.json

### Out of Scope
- Broadcast event entity (would be Phase 3)

## Technical Notes

- Bridge API: `POST /v1/broadcast` with `{"message": "...", "tags": ["primary"]}`
- Response format: `{"responses": [{"agent": "cora", "content": "..."}, {"agent": "claude", "error": "..."}]}`
- Service uses `SupportsResponse.OPTIONAL` for automation response variables

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| Empty tags list | Broadcast to all agents |
| All agents fail | Return error aggregation, no exception |
| Bridge returns empty responses | Return empty list |
| Bridge unreachable | Return error via service response |

## Dependencies

### Story Dependencies

| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| US0002 | Service | BridgeClient | Done |
| US0014 | Service | Service registration pattern | Done |

## Estimation

**Story Points:** 2
**Complexity:** Low

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-04-05 | Claude | Initial story for Phase 2 implementation |
