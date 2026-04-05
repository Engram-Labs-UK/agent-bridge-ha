# US0013: Event Platform

> **Status:** Done
> **Epic:** [EP0003: Observability & Automation](../epics/EP0003-observability-and-automation.md)
> **Owner:** Darren Benson
> **Created:** 2026-04-05

## User Story

**As a** home automation operator
**I want** event entities that fire when agents respond or invoke tools
**So that** I can build automations triggered by agent activity

## Context

Two event entities expose agent activity as HA EventEntity instances, making them visible in the automation trigger UI. `event.agent_bridge_message_received` fires each time an agent sends a response. `event.agent_bridge_tool_invoked` fires when a tool is executed, with subtypes distinguishing success from failure. Both are HA EventEntity, not raw `hass.bus` events -- this means they appear in the automation builder's entity trigger picker.

---

## Acceptance Criteria

### AC1: Message received event entity
- **Given** the event platform is loaded
- **When** the conversation agent receives a response from the bridge
- **Then** `event.agent_bridge_message_received` fires with attributes: `agent_id` (string), `model` (string), `content_preview` (string, first 200 chars), `timestamp` (ISO 8601)

### AC2: Tool invoked event entity -- success
- **Given** the event platform is loaded
- **When** a tool execution completes successfully
- **Then** `event.agent_bridge_tool_invoked` fires with event_type `tool_invoked_ok` and attributes: `agent_id` (string), `tool_name` (string), `duration_ms` (integer), `status` ("ok")

### AC3: Tool invoked event entity -- failure
- **Given** the event platform is loaded
- **When** a tool execution fails
- **Then** `event.agent_bridge_tool_invoked` fires with event_type `tool_invoked_error` and attributes: `agent_id` (string), `tool_name` (string), `duration_ms` (integer), `status` ("error")

### AC4: Event subtypes declared
- **Given** `event.agent_bridge_tool_invoked` exists
- **When** its `event_types` property is read
- **Then** it returns `["tool_invoked_ok", "tool_invoked_error"]`

### AC5: Automation trigger visibility
- **Given** both event entities are registered
- **When** creating an automation in the HA UI
- **Then** both entities appear as selectable triggers under "Entity" trigger type

### AC6: Device registry linkage
- **Given** both event entities are created
- **When** viewed in the HA device registry
- **Then** both belong to the single "Agent Bridge" device entry (created by US0012)

---

## Scope

### In Scope
- `custom_components/agent_bridge/event.py`
- Two `EventEntity` subclasses
- Helper method(s) for conversation agent and tool executor to fire events

### Out of Scope
- Discovery events (US0017 -- agent_discovered, agent_removed)
- Webhook-based real-time events (EP0005)
- The conversation agent itself (US0007)
- Tool execution logic (US0007)

---

## Technical Notes

Event entities subclass `EventEntity` from `homeassistant.components.event`. Each declares its `event_types` list. The conversation agent (US0007) and tool executor call a method on the event entity (or a shared helper) to trigger events via `self._trigger_event(event_type, attributes)`. Content preview must be truncated to 200 characters to avoid bloating HA state. Timestamps should use `dt_util.utcnow().isoformat()`.

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| Agent response has empty content | content_preview is empty string, event still fires |
| Agent response content exceeds 200 chars | content_preview truncated to 200 chars |
| Tool execution raises exception | Event fires with status "error" and tool_invoked_error subtype |
| Model field missing from bridge response | model attribute is "unknown" |
| Rapid consecutive events | All events fire; no debouncing or deduplication |
| Integration unloaded mid-conversation | Events stop firing; no error raised |

---

## Test Scenarios

- [ ] event.agent_bridge_message_received fires with correct agent_id
- [ ] event.agent_bridge_message_received fires with correct model
- [ ] event.agent_bridge_message_received content_preview truncated at 200 chars
- [ ] event.agent_bridge_message_received timestamp is valid ISO 8601
- [ ] event.agent_bridge_tool_invoked fires tool_invoked_ok on success
- [ ] event.agent_bridge_tool_invoked fires tool_invoked_error on failure
- [ ] event.agent_bridge_tool_invoked includes duration_ms as integer
- [ ] event.agent_bridge_tool_invoked event_types property returns both subtypes
- [ ] Both event entities linked to "Agent Bridge" device
- [ ] Events appear in HA automation trigger picker
- [ ] Empty content produces empty content_preview (no crash)

---

## Dependencies

### Story Dependencies
| Story | Relationship |
|-------|-------------|
| [US0005](US0005-coordinator-and-setup.md) | Requires coordinator for platform setup |
| US0007 | Conversation agent and tool executor fire events |

### External Dependencies
| Dependency | Type | Status |
|------------|------|--------|
| Home Assistant Core 2025.1.0+ | Framework | Available |
| HA EventEntity platform | Framework | Available (2025.1.0+) |

---

## Estimation

**Story Points:** 2
**Complexity:** Low

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-04-05 | Claude | Initial story generation |
