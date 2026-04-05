# US0007: Conversation Agent Core

> **Status:** Done
> **Epic:** [EP0002: Conversation & Home Control](../epics/EP0002-conversation-and-control.md)
> **Owner:** Darren Benson
> **Created:** 2026-04-05

## User Story

**As a** voice satellite or Assist UI user
**I want** the integration to register as a HA conversation agent
**So that** I can talk to bridge agents through HA's native Assist pipeline

## Context

The conversation agent is the primary interface between HA Assist and the Agent Bridge. It registers via `conversation.async_set_agent()`, builds a three-layer system prompt (room context + entity context + extra_system_prompt), routes to the correct bridge agent based on input source, and handles the full request/response cycle. Voice requests carry metadata (source, device, area, language) so agents can tailor responses.

---

## Acceptance Criteria

### AC1: Agent registration
- **Given** the integration is set up
- **When** async_setup_entry completes
- **Then** the conversation agent is registered with HA via `conversation.async_set_agent()` and appears in Assist pipeline settings

### AC2: Three-layer system prompt
- **Given** a conversation request
- **When** the system prompt is built
- **Then** it contains three layers in order: room context (if available), entity context (from US0006), and extra_system_prompt (from config, if set)

### AC3: Agent routing by source
- **Given** a config with default_agent and voice_agent set
- **When** a voice request arrives (source contains voice/satellite indicators)
- **Then** it routes to voice_agent
- **When** a text/chat request arrives
- **Then** it routes to default_agent

### AC4: Agent routing fallback
- **Given** a config with voice_agent not set (empty/None)
- **When** a voice request arrives
- **Then** it falls back to default_agent

### AC5: Voice metadata
- **Given** a voice request with device_id and/or satellite_id
- **When** the chat request is sent to the bridge
- **Then** metadata includes source: "voice", device_id, satellite_id, area (resolved), and language

### AC6: Room awareness from device registry
- **Given** a voice request with a device_id
- **When** the device is registered in HA with an area assignment
- **Then** the room context layer includes the area name (e.g. "The user is in the Kitchen")

### AC7: Room awareness from satellite_id
- **Given** a voice request with satellite_id (and no device_id area)
- **When** the satellite device has an area assignment in HA
- **Then** the room context is resolved from the satellite's area

### AC8: No room context when area unavailable
- **Given** a request where device_id/satellite_id have no area, or no device info is present
- **When** the system prompt is built
- **Then** the room context layer is omitted entirely (not an empty string or placeholder)

### AC9: Message received event
- **Given** a successful agent response
- **When** the response is processed
- **Then** an agent_bridge_message_received event fires with agent_id, model, content_preview, and timestamp

### AC10: Language passthrough
- **Given** a ConversationInput with a language field
- **When** the IntentResponse is constructed
- **Then** the language is passed through to IntentResponse and included in bridge metadata

### AC11: MATCH_ALL support
- **Given** any user utterance
- **When** HA checks supported intents
- **Then** the agent declares support for MATCH_ALL (handles all text, not specific intents)

### AC12: Unregistration on teardown
- **Given** a loaded integration
- **When** async_unload_entry is called
- **Then** the conversation agent is unregistered via `conversation.async_unset_agent()`

---

## Scope

### In Scope
- `custom_components/agent_bridge/conversation.py`
- Conversation agent class extending HA's conversation agent pattern
- System prompt builder (three layers)
- Agent routing logic (voice vs default)
- Room awareness resolution from device/satellite registries
- Voice metadata construction
- Event firing on response
- Language and MATCH_ALL support

### Out of Scope
- Tool call execution (US0008 -- called from conversation agent but logic lives in tool_executor)
- Session ID management (US0009 -- provides channel field)
- Continuation detection (US0010 -- additions to this file)
- Per-agent conversation agents (EP0004)
- SSE streaming (EP0006)

---

## Technical Notes

Use `conversation.async_set_agent(hass, entry, agent_instance)` for registration. The agent class should implement `async_process(user_input: ConversationInput) -> ConversationResult`. Room resolution: look up device_id in `dr.async_get(hass)`, get area_id from the device entry, resolve area name from `ar.async_get(hass)`. If device_id yields no area, try satellite_id. The chat request goes through BridgeClient.chat() from US0002. The response text is extracted using helpers from US0003.

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| Bridge unreachable during conversation | Return user-friendly error in ConversationResult ("Bridge is offline") |
| Agent timeout | Return "Agent is taking too long, please try again" |
| device_id not found in device registry | Skip room context, proceed without area |
| satellite_id present but device_id absent | Resolve area from satellite_id |
| Both device_id and satellite_id have different areas | Prefer satellite_id area (closer to user's physical location) |
| extra_system_prompt is empty/None | Omit third layer, do not inject empty content |
| Entity context build fails | Log error, proceed with room context only |
| voice_agent set to agent that no longer exists in bridge | Bridge handles unknown agent error; return bridge error to user |

---

## Test Scenarios

- [ ] Agent registered after setup, appears in HA conversation agents
- [ ] Agent unregistered after unload
- [ ] System prompt contains room context when area available
- [ ] System prompt contains entity context from exposure
- [ ] System prompt contains extra_system_prompt when configured
- [ ] System prompt omits room context when no area available
- [ ] System prompt omits extra_system_prompt when not configured
- [ ] Voice request routes to voice_agent
- [ ] Text request routes to default_agent
- [ ] Voice request falls back to default_agent when voice_agent not set
- [ ] Metadata includes source, device_id, satellite_id, area, language for voice
- [ ] Metadata omitted for text requests
- [ ] Room resolved from device_id area
- [ ] Room resolved from satellite_id when device_id has no area
- [ ] agent_bridge_message_received event fired on response
- [ ] Event contains agent_id, model, content_preview, timestamp
- [ ] Language passed through to IntentResponse
- [ ] MATCH_ALL declared in supported intents
- [ ] Bridge connection error returns friendly message
- [ ] Agent timeout returns friendly message

---

## Dependencies

### Story Dependencies

| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| [US0001](US0001-project-scaffold.md) | Hard | const.py, __init__.py | Done |
| [US0002](US0002-bridge-client.md) | Hard | BridgeClient.chat() | Done |
| [US0006](US0006-entity-exposure.md) | Hard | Entity exposure builder | Done |

### External Dependencies

| Dependency | Type | Status |
|------------|------|--------|
| Home Assistant Core 2025.1.0+ | Framework | Available |
| HA Conversation API (async_set_agent) | Internal API | Available |
| HA Device/Area Registries | Internal API | Available |

---

## Estimation

**Story Points:** 5
**Complexity:** High

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-04-05 | Claude | Initial story generation |
