# Product Requirements Document

**Project:** Agent Bridge HA
**Version:** 0.1.0
**Last Updated:** 2026-06-01
**Status:** Complete (v0.1 spec — see review banner)
**Last Review:** 2026-06-01 — reconcile + prd/trd/tsd review against bridge v4.36 + current HA APIs (CR-0002 redesign basis)

> ⚠️ **Review banner (2026-06-01):** This PRD documents the **v0.1** design, which targets "Agent Bridge v3.1.0+". The bridge is now **v4.36.0** and Home Assistant's conversation APIs have moved on by ~12 release cycles. A verified audit found the **reactive home-control path is structurally inert** — it never actuates (neither HA nor the v4.36 bridge carries a `tool_calls` contract), and the component sits on HA's legacy `AbstractConversationAgent`. The redesign is **[CR-0002](change-requests/cr0002.md)** + **[EP0007](epics/EP0007-bridge-v436-modern-ha-realignment.md)** (actuation via HA's Assist **LLM API / MCP**; `ConversationEntity` + `ChatLog`; bridge-client re-alignment). The §-level content below is **retained as the v0.1 record** and will be rewritten to the redesigned model by **US0030**. Stale topology references ("agentbox02", "7+ agents", port-only) → now **AB01 primary + AB03 standby**, ~14+ agents; verify live via `GET /v1/discovery`.

---

## 1. Project Overview

### Product Name
Agent Bridge HA

### Purpose
A Home Assistant custom component that connects any AI agent registered on an Agent Bridge instance to Home Assistant's conversation, voice, and automation frameworks. Agents appear as native HA conversation agents with full entity exposure, room awareness, health monitoring, and automation events. The integration is the first in a planned `agent-bridge-*` ecosystem of platform adapters.

### Tech Stack
- **Language:** Python 3.12+
- **Framework:** Home Assistant Core 2025.1.0+ (custom component)
- **HTTP Client:** aiohttp (HA's bundled async HTTP library)
- **Validation:** voluptuous (HA's standard config validation)
- **Testing:** pytest, pytest-homeassistant-custom-component
- **Distribution:** HACS (Home Assistant Community Store)

### Architecture Pattern
HA custom component (thin adapter) with bridge-side intelligence. The component follows HA conventions (config flow, DataUpdateCoordinator, entity platforms) and delegates routing, resilience, and agent management to the Agent Bridge.

### Deployment
Installed via HACS custom repository or manual copy to `custom_components/agent_bridge/`. No containers, no separate processes. Runs inside the HA Python runtime.

---

## 2. Problem Statement

### Problem Being Solved
The homelab runs multiple AI agents (Cora, Claude/Spanners, Prof, Knox, Quill) behind an Agent Bridge. Currently, Home Assistant has limited integration: REST sensors for health, REST commands for chat, and a forked OpenClaw integration that only talks to one agent via the OpenClaw gateway. There is no way to:

- Use multiple bridge agents as separate HA conversation agents (e.g. Cora for kitchen voice, Claude for study)
- Expose HA entity state to agents so they understand what devices exist and their current state
- Inject room/area context into voice requests so agents know where commands originate
- Monitor per-agent health natively in HA dashboards
- Trigger HA automations from agent events (health changes, tool invocations, messages)

The OpenClaw HA integration has excellent patterns for entity exposure and conversation agent registration, but it is tightly coupled to the OpenClaw gateway protocol and supports only a single agent at a time.

### Target Users
1. **Darren (operator)** -- Configures the integration, assigns agents to voice satellites, builds agent-aware automations
2. **Voice satellite users** -- Family members issuing voice commands via Assist pipeline, routed through bridge agents
3. **Home Assistant automations** -- Scripts and automations that send messages to agents or react to agent events
4. **Agent Bridge agents** -- AI agents that receive HA entity context in their system prompts, enabling smart home control

### Context
The Agent Bridge (Engram-Labs-UK/agent-bridge) is live on agentbox02 (port 18780) with 7+ registered agents. It exposes an OpenAI-compatible chat API, discovery endpoints, per-agent health, webhooks, and tool invocation. The existing OpenClaw HA fork (DarrenBenson/OpenClawHomeAssistantIntegration) provides battle-tested patterns for entity exposure, conversation agent registration, room awareness, and coordinator-based polling. This project cherry-picks those patterns and rewires them for the Agent Bridge protocol.

This is the first `agent-bridge-*` platform adapter. The naming convention (`agent-bridge-ha`, `agent-bridge-n8n`, `agent-bridge-obsidian`) establishes an ecosystem pattern. The bridge's OpenAPI spec at `/v1/openapi.json` is the binding contract for all adapters.

---

## 3. Feature Inventory

| Feature | Description | Priority | Epic |
|---------|-------------|----------|------|
| Bridge Client | Async HTTP client for Agent Bridge REST API (includes response text extraction and auth refresh handling) | P0 | EP0001 |
| Config Flow | HA UI setup with bridge discovery and agent selection | P0 | EP0001 |
| Data Coordinator | Periodic polling of bridge health and agent status | P0 | EP0001 |
| Primary Conversation Agent | Single conversation agent using bridge default routing (includes voice source signalling) | P0 | EP0002 |
| Entity Exposure | Format HA entity state as AI-consumable context | P0 | EP0002 |
| Room Awareness | Inject device area into voice request prompts | P0 | EP0002 |
| HA Service Execution | Execute HA services from agent tool_call responses | P0 | EP0002 |
| Session Persistence | Agent-scoped sessions survive HA restarts | P1 | EP0002 |
| Bridge Health Sensors | Bridge status, connectivity, agent count sensors | P0 | EP0003 |
| Event Entities | HA events for agent messages and tool invocations | P1 | EP0003 |
| Services | send_message and invoke_tool HA services | P1 | EP0003 |
| Voice Debug Logging | Detailed logging of voice routing decisions | P1 | EP0003 |
| Per-Agent Conversation Agents | Each bridge agent as a selectable HA conversation agent | P1 | EP0004 |
| Per-Agent Health Sensors | Binary sensors per agent from deep health check | P1 | EP0004 |
| Dynamic Agent Discovery | Auto-update entities when bridge agents change | P1 | EP0004 |
| Webhook Integration | Subscribe to bridge events for real-time HA updates | P2 | EP0005 |
| Broadcast Service | Send message to multiple agents via bridge broadcast | P2 | EP0005 |
| SSE Streaming | Stream agent responses for lower-latency voice | P2 | EP0006 |
| Continuation Detection | Detect agent questions for multi-turn voice dialogue | P2 | EP0006 |

### Feature Details

#### Bridge Client

**User Story:** As the integration, I want an async HTTP client that speaks the Agent Bridge REST API so that all bridge communication goes through a single, well-tested client.

**Acceptance Criteria:**
- [x] Async aiohttp client with configurable base URL, bearer token, and timeout
- [x] `discover()` calls `GET /v1/discovery` and returns agent list with capabilities and health
- [x] `chat(messages, agent, channel)` calls `POST /v1/chat/completions` with proper request body
- [x] `health(depth)` calls `GET /health?depth={shallow|deep}` and returns typed response
- [x] `invoke_tool(agent_id, tool_name, args)` calls `POST /v1/tools/invoke`
- [x] `check_alive()` lightweight connectivity check via `GET /health`
- [x] Bearer token sent in `Authorization` header on all authenticated requests
- [x] Connection errors raise typed exceptions (BridgeConnectionError, BridgeAuthError, BridgeTimeoutError)
- [x] SSL/TLS support with optional certificate verification bypass for self-signed certs
- [x] Uses HA's shared `aiohttp.ClientSession` (via `async_get_clientsession()`) rather than creating its own
- [x] Response text extraction handles nested/varying structures: priority keys `text`, `content`, `message`, `output_text` with recursive traversal up to 8 levels
- [x] Extracts `tool_calls` from chat completion responses when present (for HA service execution)
- [x] Auth failure (401/403) triggers config entry reload notification so user can update token

**Dependencies:** None (foundation)
**Status:** Complete
**Confidence:** [HIGH]

#### Config Flow

**User Story:** As Darren, I want to set up the integration via the HA UI by entering the bridge URL and token, then selecting which agents to expose, so that setup is guided and validated.

**Acceptance Criteria:**
- [x] Step 1: Enter bridge URL (default: `http://localhost:18780`) and bearer token
- [x] Step 1 validates connectivity by calling `GET /health`
- [x] Step 1 validates authentication by calling `GET /v1/discovery` (requires auth)
- [x] Step 2: Shows discovered agents with name, description, and health status
- [x] Step 2: User selects default chat agent and default voice agent from discovered list
- [x] Options flow allows changing default agents, context limits, and feature toggles post-setup
- [x] Options flow: context_max_chars (1000-200000, default 13000)
- [x] Options flow: context_strategy (truncate or clear, default truncate)
- [x] Options flow: enable_per_agent_entities (boolean, default false)
- [x] Options flow: enable_tool_calls (boolean, default true)
- [x] Options flow: thinking_timeout (10-3600 seconds, default 120)
- [x] Options flow: ssl_verify (boolean, default true)
- [x] Options flow: debug_logging (boolean, default false)
- [x] Config entry stores bridge URL, token, selected agents, and all options

**Dependencies:** Bridge Client
**Status:** Complete
**Confidence:** [HIGH]

#### Data Coordinator

**User Story:** As the integration, I want to periodically poll the bridge for health and agent status so that HA entities stay up to date without overwhelming the bridge.

**Acceptance Criteria:**
- [x] Extends HA's `DataUpdateCoordinator` with configurable poll interval (default 30s)
- [x] Polls `GET /health?depth=shallow` for bridge status and agent counts
- [x] Polls `GET /v1/discovery` for agent list with capabilities and health (less frequent, every 5 min)
- [x] Caches last-known-good data for first 3 consecutive failures (graceful degradation)
- [x] Exposes typed data dict: bridge_status, agent_count, agents, last_activity
- [x] Triggers entity updates via standard HA coordinator callback

**Dependencies:** Bridge Client
**Status:** Complete
**Confidence:** [HIGH]

#### Primary Conversation Agent

**User Story:** As a voice satellite user, I want to talk to an AI agent via HA Assist so that voice commands are processed by the bridge's default agent with full awareness of my home's entities and the room I'm in.

**Acceptance Criteria:**
- [x] Registers as HA conversation agent via `conversation.async_set_agent()`
- [x] Selectable in HA Assist pipeline settings (voice assistants)
- [x] Receives `ConversationInput` and returns `ConversationResult`
- [x] Builds system prompt with exposed entity context (from entity exposure feature)
- [x] Injects device area name into system prompt for room awareness
- [x] Includes `extra_system_prompt` from `ConversationInput` if provided by the pipeline
- [x] Sends to bridge via `POST /v1/chat/completions` with `agent` field set to configured default
- [x] Voice requests use configured `voice_agent` if different from chat agent
- [x] Voice requests include `source: "voice"` metadata in chat request so agents can format responses for speech (concise, no markdown tables)
- [x] Includes `device_id`, `satellite_id`, and resolved `area_name` in chat request metadata so agents have full device context
- [x] Passes `user_input.language` to `IntentResponse` for correct TTS language routing
- [x] Supports all HA-supported languages via `MATCH_ALL` (delegates translation to the AI model)
- [x] Fires `agent_bridge_message_received` event with response content, agent ID, and model

**Dependencies:** Bridge Client, Entity Exposure
**Status:** Complete
**Confidence:** [HIGH]

#### Entity Exposure

**User Story:** As an AI agent receiving a voice command, I want to know what devices exist in the home, their current state, and which room they're in, so that I can accurately control the home.

**Acceptance Criteria:**
- [x] Uses HA's native entity exposure settings (Settings > Voice assistants > Expose)
- [x] Formats exposed entities with: entity_id, friendly_name, state, area, and relevant attributes
- [x] Relevant attributes include: brightness, colour_temp, temperature, target_temperature, volume, battery_level, media_title
- [x] Caps at 250 entities per prompt (configurable via options)
- [x] Context string truncated or cleared per context_strategy option (truncate or clear)
- [x] Context built fresh per request (not cached) to reflect current state
- [x] Uses the conversation agent's entity exposure settings from HA's Voice Assistants configuration (Settings > Voice assistants > Expose)

**Dependencies:** None (HA framework)
**Status:** Complete
**Confidence:** [HIGH]

#### Room Awareness

**User Story:** As a voice satellite user, I want the agent to know which room my command came from so that "turn on the lights" means the lights in my room, not the whole house.

**Acceptance Criteria:**
- [x] Extracts device area from `ConversationInput.device_id` via HA device registry
- [x] Also handles `ConversationInput.satellite_id` (HA 2025+) for multi-mic arrays where satellite_id differs from device_id
- [x] Injects area name into system prompt: "The user is in the {area_name}."
- [x] When no device area available (e.g. text input, unassigned device), omits room context (does not guess)
- [x] Area context appears before entity list in the system prompt

**Dependencies:** Primary Conversation Agent
**Status:** Complete
**Confidence:** [HIGH]

#### HA Service Execution

**User Story:** As a voice satellite user, I want the agent to actually control my home (turn on lights, set thermostats, lock doors) when I ask, not just describe what it would do.

**Acceptance Criteria:**
- [x] When agent response includes `tool_calls` in the OpenAI chat completion format, the integration intercepts and executes them
- [x] Supports `execute_service` tool call: extracts `domain`, `service`, `entity_id` (or `target` dict) and calls `hass.services.async_call()`
- [x] Supports `execute_services` (plural) for batched multi-entity commands in a single response
- [x] Tool call results (success/failure) are sent back to the agent as tool_call result messages for final response formulation
- [x] Only exposed entities can be targeted (validates entity_id against exposure list before execution)
- [x] Tool execution gated behind `enable_tool_calls` option (default: true)
- [x] Each tool execution fires `agent_bridge_tool_invoked` event with: tool_name, entity_id, status, duration_ms
- [x] Failed tool calls return descriptive error to agent (e.g. "Entity light.kitchen not found") rather than raising an exception
- [x] Tool execution timeout of 10 seconds per service call (prevents hanging on unresponsive devices)

**Dependencies:** Primary Conversation Agent, Entity Exposure
**Status:** Complete
**Confidence:** [HIGH]

#### Bridge Health Sensors

**User Story:** As Darren, I want HA sensors showing bridge health, connectivity, and agent count so that I can build dashboards and trigger automations when the bridge degrades.

**Acceptance Criteria:**
- [x] `sensor.agent_bridge_status` -- bridge health status (ok, degraded, error) with version and uptime as attributes
- [x] `binary_sensor.agent_bridge_connected` -- bridge connectivity (on/off)
- [x] `sensor.agent_bridge_agent_count` -- number of healthy agents with total as attribute
- [x] All sensors update via DataUpdateCoordinator (no independent polling)
- [x] Sensors link to a single "Agent Bridge" device in HA device registry

**Dependencies:** Data Coordinator
**Status:** Complete
**Confidence:** [HIGH]

#### Event Entities

**User Story:** As an automation builder, I want HA events fired when agents respond or invoke tools so that I can trigger automations based on agent activity.

**Acceptance Criteria:**
- [x] `event.agent_bridge_message_received` fires on agent response with: agent_id, model, content_preview, timestamp
- [x] `event.agent_bridge_tool_invoked` fires on tool invocation with subtypes: `tool_invoked_ok`, `tool_invoked_error`
- [x] Tool event includes: agent_id, tool_name, duration_ms, status
- [x] Events are HA event entities (visible in automation trigger UI)

**Dependencies:** Primary Conversation Agent
**Status:** Complete
**Confidence:** [HIGH]

#### Services

**User Story:** As an automation builder, I want HA services to send messages to specific agents and invoke tools so that I can build agent-powered automations.

**Acceptance Criteria:**
- [x] `agent_bridge.send_message` service with fields: message (required), agent_id (optional, defaults to default agent), session_id (optional)
- [x] `agent_bridge.invoke_tool` service with fields: agent_id (required), tool_name (required), args (optional object)
- [x] Services return response data accessible in automation `response_variable`
- [x] Services validate agent_id exists via coordinator's cached agent list
- [x] Services fire corresponding event entities on completion

**Dependencies:** Bridge Client, Data Coordinator
**Status:** Complete
**Confidence:** [HIGH]

#### Per-Agent Conversation Agents

**User Story:** As Darren, I want each bridge agent to appear as a separate conversation agent in HA so that I can assign Cora to the kitchen satellite and Claude to the study satellite.

**Acceptance Criteria:**
- [x] When `enable_per_agent_entities` is true, each bridge agent with `chat: true` capability gets a conversation agent entity
- [x] Each conversation agent identified as `conversation.agent_bridge_{agent_id}`
- [x] Each agent's conversation entity uses the same entity exposure and room awareness logic
- [x] Per-agent conversation agents route via `agent` field in chat request (not bridge default)
- [x] Agents added/removed from bridge are reflected in HA within one discovery poll cycle
- [x] Removed agents' entities are marked unavailable (not deleted, to preserve automations)

**Dependencies:** Primary Conversation Agent, Dynamic Agent Discovery
**Status:** Complete
**Confidence:** [MEDIUM]

#### Per-Agent Health Sensors

**User Story:** As Darren, I want a binary sensor per agent showing healthy/unhealthy so that I can build dashboards and automations per agent.

**Acceptance Criteria:**
- [x] When `enable_per_agent_entities` is true, each agent gets `binary_sensor.agent_bridge_{agent_id}_healthy`
- [x] On = healthy, Off = unhealthy (matches HA connectivity device class)
- [x] Attributes include: adapter type, last response time, circuit breaker state
- [x] Data sourced from `GET /health?depth=deep` (polled less frequently, every 60s)
- [x] New agents get sensors created; removed agents get sensors marked unavailable

**Dependencies:** Data Coordinator, Per-Agent Conversation Agents
**Status:** Complete
**Confidence:** [MEDIUM]

#### Dynamic Agent Discovery

**User Story:** As the integration, I want to detect when agents are added or removed from the bridge so that HA entities stay in sync without manual reconfiguration.

**Acceptance Criteria:**
- [x] Compares current discovery response against previous on each poll cycle
- [x] New agents: creates conversation agent entity and health sensor (if per-agent enabled)
- [x] Removed agents: marks entities as unavailable
- [x] Changed agents: updates entity attributes (description, capabilities)
- [x] Emits HA event `agent_bridge_agent_discovered` and `agent_bridge_agent_removed`

**Dependencies:** Data Coordinator
**Status:** Complete
**Confidence:** [MEDIUM]

#### Webhook Integration

**User Story:** As the integration, I want real-time agent health updates from the bridge via webhooks so that HA reacts instantly to agent outages instead of waiting for the next poll.

**Acceptance Criteria:**
- [x] On setup, registers a webhook with the bridge: `POST /v1/webhooks` subscribing to `agent:health-changed`
- [x] HA webhook endpoint receives bridge events and updates coordinator data immediately
- [x] Webhook registration refreshed on HA restart
- [x] Falls back to polling if webhook registration fails (graceful degradation)
- [x] Unregisters webhook on integration unload

**Dependencies:** Data Coordinator, Bridge Client
**Status:** Complete
**Confidence:** [LOW]

#### Broadcast Service

**User Story:** As an automation builder, I want to send a message to all agents (or a tagged subset) in one service call so that system-wide instructions don't need per-agent automations.

**Acceptance Criteria:**
- [x] `agent_bridge.broadcast` service with fields: message (required), tags (optional list)
- [x] Calls `POST /v1/broadcast` on the bridge
- [x] Returns aggregated responses from all targeted agents
- [x] Individual agent failures reported in response without blocking others

**Dependencies:** Bridge Client, Services
**Status:** Complete
**Confidence:** [HIGH]

#### SSE Streaming

**User Story:** As a voice satellite user, I want agent responses to stream so that I hear the first words sooner rather than waiting for the complete response.

**Acceptance Criteria:**
- [x] Bridge client supports Server-Sent Events (SSE) streaming from chat completions
- [x] Conversation agent attempts streaming first, falls back to non-streaming on failure
- [x] Partial content assembled into complete ConversationResult
- [x] Streaming timeout configurable (default 300 seconds)

**Dependencies:** Bridge Client, Primary Conversation Agent
**Status:** Complete
**Confidence:** [MEDIUM]

#### Continuation Detection

**User Story:** As a voice satellite user, I want the agent to keep listening when it asks a follow-up question so that multi-turn voice dialogue works naturally.

**Acceptance Criteria:**
- [x] Analyses the final sentence of the agent response for question patterns
- [x] Triggers continuation when: final sentence ends with `?` AND contains no words from the exclusion list
- [x] Default continuation phrases (matched case-insensitively): "would you like", "shall I", "do you want", "should I", "which one", "what would you prefer"
- [x] Default exclusion list (suppress continuation): "right?", "isn't it?", "okay?", "yeah?", "let me know if you need anything"
- [x] Both lists configurable via a `continuation_phrases` / `continuation_exclusions` option
- [x] Returns `continue_conversation: True` in ConversationResult when continuation is detected

**Dependencies:** Primary Conversation Agent
**Status:** Complete
**Confidence:** [MEDIUM]

#### Session Persistence

**User Story:** As a voice satellite user, I want my conversation context to survive Home Assistant restarts so that the agent remembers what we were discussing.

**Acceptance Criteria:**
- [x] Agent-scoped session IDs generated on first conversation per agent (format: `agent:{agent_id}:assist_{random_hex}`)
- [x] Session IDs persisted to HA Store (`.storage/agent_bridge.sessions`)
- [x] Sessions loaded on integration startup, reused for subsequent conversations
- [x] Session ID sent to bridge as `channel` field in chat request (bridge manages conversation history)
- [x] One session per agent (not per conversation_id) to maintain continuous context

**Dependencies:** Primary Conversation Agent
**Status:** Complete
**Confidence:** [HIGH]

#### Voice Debug Logging

**User Story:** As Darren debugging voice routing issues, I want detailed logs showing which agent handled a voice request, what session was used, and what room context was detected.

**Acceptance Criteria:**
- [x] When `debug_logging` option is enabled, logs: resolved agent ID, session ID, area name, device_id, satellite_id for each voice request
- [x] Log level is `info` (not debug) so it appears in default HA logs without adjusting log levels
- [x] Sensitive data (token, full prompt) never logged even in debug mode
- [x] Configurable via options flow (default: off)

**Dependencies:** Primary Conversation Agent
**Status:** Complete
**Confidence:** [HIGH]

---

## 4. Functional Requirements

### Core Behaviours
- The integration communicates exclusively with the Agent Bridge REST API -- never directly with individual agents
- All HTTP communication is async (aiohttp) and non-blocking
- Entity exposure builds fresh context per request to reflect current HA state
- The bridge handles agent routing, failover, and circuit breaking -- the integration trusts the bridge's decisions
- Config entry data is the single source of truth for bridge connection details
- Voice requests are explicitly tagged as voice origin so agents can adapt response format (concise, TTS-friendly, no markdown tables or code blocks)

### Input/Output Specifications

**Conversation Input (from HA pipeline):**
- User text message from Assist pipeline or automation
- Device ID (for room awareness)
- Satellite ID (for multi-mic arrays, HA 2025+)
- Conversation ID (for multi-turn context)
- Language (for TTS routing)
- Extra system prompt (optional pipeline-injected instructions)

**Conversation Output (to HA pipeline):**
- Agent response text (set as IntentResponse speech)
- Language (passed through from input)
- Conversation ID (agent-scoped session)
- Continue conversation flag (from continuation detection)
- Agent ID that responded
- Model used

**Service Input (send_message):**
- Message text (required)
- Agent ID (optional)
- Session ID (optional)

**Service Output:**
- Agent response text
- Agent ID
- Model used

### Business Logic Rules
- If bridge is unreachable during conversation, return a user-friendly error message (not a stack trace)
- If configured voice agent is unhealthy, fall back to default chat agent
- Entity exposure respects HA's native expose settings -- the integration does not override user choices
- Per-agent entities are only created for agents with `chat: true` capability

---

## 5. Non-Functional Requirements

### Performance
- Bridge client timeout: 120 seconds default (AI agents can be slow)
- Thinking timeout: configurable 10-3600 seconds for long-running agent tasks
- Entity exposure context must build in < 500ms for up to 250 entities
- Coordinator polling must not block the HA event loop

### Security
- Bearer token stored in HA's encrypted config entry storage (not plaintext files)
- Token never logged or exposed in diagnostics
- SSL/TLS supported for bridge connections
- Self-signed certificate bypass available but off by default

### Scalability
- Supports up to 20 bridge agents (practical limit for homelab)
- Entity exposure caps at 250 entities to avoid prompt bloat
- Coordinator poll interval adjustable to reduce bridge load

### Availability
- Graceful degradation: if bridge is down, sensors show offline status, conversation returns error message
- Cached data survives transient bridge outages (3 consecutive failures before marking offline)
- Integration unload cleans up all resources (webhook subscriptions, coordinator timers)

---

## 6. AI/ML Specifications

### Models and Providers
The integration does not manage AI models directly. All model selection, routing, and inference happens on the Agent Bridge. The integration sends messages and receives responses -- it is model-agnostic.

### Prompt Patterns
- **System prompt:** Composed of entity context + room awareness + optional extra context
- **Entity context format:** One line per entity: `{friendly_name} ({entity_id}): {state} [area: {area}] [brightness: {brightness}]`
- **Room awareness:** Prepended line: "The user is in the {area_name}."
- **No model-specific tuning:** The bridge and agents handle prompt engineering

### Context Management
- Entity context rebuilt per request (stateless)
- Conversation history managed by bridge channels (not by the integration)
- Context truncation at configurable max_chars to prevent prompt overflow

---

## 7. Data Architecture

### Data Models

**Config Entry Data:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| bridge_url | string | Yes | - | Bridge base URL (e.g. http://10.0.0.206:18780) |
| bridge_token | string | Yes | - | Bearer token for bridge auth |
| default_agent | string | Yes | - | Agent ID for default chat routing |
| voice_agent | string | No | default_agent | Agent ID for voice requests |
| context_max_chars | int | No | 13000 | Max entity context length |
| context_strategy | string | No | truncate | How to handle context overflow (truncate or clear) |
| enable_per_agent_entities | bool | No | false | Create per-agent conversation agents and sensors |
| enable_tool_calls | bool | No | true | Allow agents to invoke tools |
| thinking_timeout | int | No | 120 | Timeout for agent response in seconds |
| ssl_verify | bool | No | true | Verify SSL certificates |
| debug_logging | bool | No | false | Log voice routing decisions (agent, session, area) |

**Coordinator Data:**

| Field | Type | Description |
|-------|------|-------------|
| bridge_status | string | ok, degraded, error |
| bridge_version | string | Bridge software version |
| bridge_uptime | int | Seconds since bridge start |
| agent_count_healthy | int | Healthy agent count |
| agent_count_total | int | Total agent count |
| agents | list[AgentInfo] | Per-agent details from discovery |
| connected | bool | Bridge reachable |
| last_poll | datetime | Last successful poll timestamp |

**AgentInfo:**

| Field | Type | Description |
|-------|------|-------------|
| id | string | Agent identifier |
| name | string | Display name |
| description | string | Agent description |
| healthy | bool | Agent health status |
| adapter | string | Adapter type (http-openai, cli, etc.) |
| capabilities | dict | Agent capabilities (chat, tools, streaming) |
| tags | list[string] | Agent tags |

**Session Data:**

| Field | Type | Description |
|-------|------|-------------|
| sessions | dict[str, str] | Map of agent_id to session_id |

Session ID format: `agent:{agent_id}:assist_{random_hex}` (e.g. `agent:cora:assist_a1b2c3d4`)

### Storage Mechanisms
- Config entry: HA's built-in encrypted storage (`.storage/`)
- Session IDs: HA Store (`.storage/agent_bridge.sessions`), persists across restarts
- Coordinator state: in-memory only (rebuilt from bridge on each poll)
- Conversation history: delegated to bridge channels (not stored in HA)
- Entity exposure: computed per request (not stored)

---

## 8. Integration Map

### External Services

| Service | Purpose | Protocol | Auth |
|---------|---------|----------|------|
| Agent Bridge | Agent communication, discovery, health | REST (HTTP/HTTPS) | Bearer token |
| Home Assistant Core | Entity registry, device registry, area registry, conversation API | Internal Python API | N/A |

### Authentication Methods
- Agent Bridge: Bearer token in `Authorization` header
- HA Core: Internal API (no auth needed within the same process)

### Third-Party Dependencies
- `aiohttp` -- Async HTTP client (bundled with HA)
- `voluptuous` -- Config validation (bundled with HA)
- No additional pip packages required (HA provides everything needed)

---

## 9. Configuration Reference

### Environment Variables

No environment variables. All configuration via HA config entry (UI-driven).

### Feature Flags

| Flag | Scope | Default | Description |
|------|-------|---------|-------------|
| enable_per_agent_entities | Options flow | false | Create per-agent conversation agents and health sensors |
| enable_tool_calls | Options flow | true | Allow tool invocation service and events |
| ssl_verify | Options flow | true | Verify bridge SSL certificates |

---

## 10. Quality Assessment

### Tested Functionality
No automated tests exist yet. All Phase 1 features (EP0001-EP0004) are implemented but untested. See TSD for test strategy.

### Untested Areas
Entire codebase -- 2,255 lines of Python across 13 modules with 0% test coverage.

### Technical Debt
- No test suite (0% coverage vs 90% target)
- No CI/CD pipeline (GitHub Actions workflow not yet created)

---

## 11. Open Questions

- [x] **Q:** Should the integration register a webhook with the bridge on setup, or is polling sufficient for homelab scale?
  **Context:** Webhooks give real-time health updates but add complexity (HA needs a reachable callback URL). Polling at 30s is probably fine for homelab.
  **Decision:** Polling only in Phase 1 (EP0001-EP0004). Webhook Integration deferred to EP0005 (P2). See ADR-002 in TRD.

- [x] **Q:** Should per-agent conversation entities be dynamic (auto-created from discovery) or user-selected in config flow?
  **Context:** Dynamic is more automated but creates entity churn if agents come and go. User-selected is more controlled. Current design has tension: `enable_per_agent_entities` gates creation (user-controlled), but Dynamic Agent Discovery AC says entities auto-update within one poll cycle (implies fully dynamic once enabled).
  **Decision:** Hybrid -- user enables the feature via `enable_per_agent_entities` flag, then all discovered agents with `chat: true` get entities automatically. Discovery drives the list, the flag is the on/off switch. Implemented in conversation.py and binary_sensor.py.

- [x] **Q:** Should the integration manage bridge channels for conversation persistence, or let the bridge handle it entirely?
  **Context:** Bridge channels provide multi-turn context. The integration could create a channel per HA conversation ID, or let the bridge use ephemeral sessions.
  **Decision:** Integration creates one agent-scoped session per agent, persisted to HA Store. Session ID sent as `channel` field. See Session Persistence feature (EP0002).

---

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2026-04-05 | 0.1.0 | Initial PRD -- greenfield project definition |
| 2026-04-05 | 0.1.1 | RV0001 review: fixed voice_agent naming inconsistency in Primary Conversation Agent AC |
| 2026-04-05 | 0.1.2 | PRD review: merged 3 sub-features into parents (22→19 features), reordered table by epic, fixed Entity Exposure AC7, made Continuation Detection AC4 concrete, added Session data model, resolved Open Questions Q1 and Q3 |
| 2026-04-05 | 0.1.3 | RV0005 review: updated 16 Phase 1 feature statuses Not Started→Complete (code exists), ticked all Phase 1 AC checkboxes, resolved Open Question Q2 (hybrid approach implemented), updated Quality Assessment with actual coverage (0%) |

---

> **Confidence Markers:** [HIGH] clear requirements | [MEDIUM] inferred from patterns | [LOW] speculative
>
> **Status Values:** Complete | Partial | Stubbed | Broken | Not Started
