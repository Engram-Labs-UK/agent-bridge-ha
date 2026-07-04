# Product Requirements Document

**Project:** Agent Bridge HA
**Version:** 0.1.0
**Last Updated:** 2026-07-04
**Status:** Complete (reconciled to shipped code — see currency note)
**Last Review:** 2026-07-04 — CR-0011 full reconcile against the shipped integration (bridge v4.141.0 / HA 2026.2.3 baseline)

> **Currency note (CR-0011, 2026-07-04):** This PRD was fully reconciled against the shipped code (0.11.x on this branch; tested baseline **bridge v4.141.0 / HA 2026.2.3**, per `const.TESTED_*`). The feature inventory, feature details, and data models below describe **reality as shipped** — the post-EP0007 `ConversationEntity`/`ChatLog` design with agent-side actuation (Option A), the CR-0009/CR-0010 observability + memory features, and the SPRINT-2026-07-04 hardening pass (CR-0012..CR-0016, BG0012). Superseded v0.1 designs (the HA-side tool-execution loop, HA-Store session persistence, the removed option flags) have been **rewritten**, not struck through; the v0.1 record lives in git history. The 2026-06-01 audit that triggered the redesign is [CR-0002](change-requests/cr0002.md) + [EP0007](epics/EP0007-bridge-v436-modern-ha-realignment.md).

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
| Bridge Client | Async HTTP client for Agent Bridge REST API (typed errors, URL-encoded path parameters per CR-0015) | P0 | EP0001 |
| Config Flow | HA UI setup with bridge discovery, agent selection, and a first-run SSL-verify toggle (CR-0016) | P0 | EP0001 |
| Data Coordinator | Periodic polling of bridge health, discovery, usage, and fleet-doctor data | P0 | EP0001 |
| Conversation Entities | One `ConversationEntity` per bridge agent (config subentries), forwarding utterance + grounding + `caller_context` | P0 | EP0002/EP0007 |
| Entity Exposure | Format HA entity state as an AI grounding hint (fail-closed) | P0 | EP0002 |
| Room Awareness | Inject device area/floor into the caller-context envelope and system prompt | P0 | EP0002 |
| Agent-Side Actuation (Option A) | Agent actuates HA via its own `/api/mcp` mount; HA fires `agent_bridge_actuation_audit` per reactive turn | P0 | EP0007 |
| Session Continuity | Idle-windowed bridge channel keys; the bridge persists per-channel context (24h TTL) | P1 | US0032/CR-0013 |
| Usage & Cost Sensors | Per-agent token + estimated GBP cost sensors from `/v1/agents/{id}/usage` | P2 | CR-0009 |
| Fleet-Doctor Diagnostics & Repair | `/v1/doctor` verdict in coordinator data; opt-in HA repair issue on CRITICAL (CR-0012) | P2 | CR-0009 |
| Diagnostics Platform | Redacted config-entry diagnostics download (doctor, usage, agents, tool surface) | P2 | CR-0009 |
| Agent Memory Services | `agent_bridge.memory_record` / `memory_recall` | P2 | CR-0010 |
| Bridge Health Sensors | Bridge status, connectivity, agent count sensors | P0 | EP0003 |
| Event Entities | HA events for agent messages; actuation audit event per reactive turn | P1 | EP0003 |
| Services | send_message, invoke_tool, broadcast, ask_with_image, announce, memory services (default-agent fallback, `ServiceValidationError` semantics — CR-0016) | P1 | EP0003 |
| Voice Debug Logging | Turn routing logged at debug level via HA's per-entry debug logging (CR-0013 removed the toggle) | P1 | EP0003 |
| Per-Agent Conversation Agents | Each bridge agent added as a config subentry becomes a selectable HA conversation agent | P1 | EP0004 |
| Dynamic Agent Discovery | Crew-aware discovery (`?include=crew`); events fired when bridge agents change | P1 | EP0004 |
| Webhook Integration | Hardened bridge-event webhook: local-only, POST-only, persistent id, validated pushes (CR-0014) | P2 | EP0005 |
| Broadcast Service | Send message to multiple agents via bridge broadcast | P2 | EP0005 |
| SSE Streaming | Opt-in streaming of replies to TTS, with confirm-marker strip (BG0012) | P2 | EP0006 |
| Continuation Detection | Detect agent questions for multi-turn voice dialogue | P2 | EP0006 |
| AI Tasks | One `ai_task` entity per agent for `ai_task.generate_data` (structured data / summaries) | P2 | US0039 |

### Feature Details

#### Bridge Client

**User Story:** As the integration, I want an async HTTP client that speaks the Agent Bridge REST API so that all bridge communication goes through a single, well-tested client.

**Acceptance Criteria:**
- [x] Async aiohttp client with configurable base URL, bearer token, and timeout
- [x] `discover(include=["crew"])` calls `GET /v1/discovery?include=crew` and returns the agent list with capabilities, health, and per-agent crew membership (CR-0003)
- [x] `chat(messages, agent, channel, caller_context, attachments)` calls `POST /v1/chat/completions`; `chat_stream(...)` streams the v4.36 SSE shape
- [x] `health(depth)` calls `GET /health?depth={shallow|deep}`; `agent_health()` calls the auth-gated `GET /v1/health` (tri-state + `toolSurface`/`readOnlySafe`)
- [x] `invoke_tool(agent_id, tool_name, args)` calls `POST /v1/tools/invoke` with the v4.36 `agent`/`tool` body
- [x] Observability + memory methods: `agent_usage()` (`GET /v1/agents/{id}/usage`), `doctor()` (`GET /v1/doctor`), `memory_record()`/`memory_recall()` (`POST`/`GET /v1/agents/{id}/memory`), `agent_context()` (`GET /v1/agent-context`)
- [x] Path parameters (agent ids, subscription ids) are URL-encoded before interpolation (CR-0015)
- [x] `check_alive()` lightweight connectivity check via `GET /health`
- [x] Bearer token sent in `Authorization` header on all authenticated requests; `x-bridge-mcp-caller` identifies the caller agent (BG0004)
- [x] Connection errors raise typed exceptions (BridgeConnectionError, BridgeAuthError, BridgeCallerError, BridgeTimeoutError)
- [x] SSL/TLS support with optional certificate verification bypass for self-signed certs
- [x] Uses HA's shared `aiohttp.ClientSession` (via `async_get_clientsession()`) rather than creating its own
- [x] Response text extraction handles nested/varying structures: priority keys `text`, `content`, `message`, `output_text` with recursive traversal up to 8 levels

**Dependencies:** None (foundation)
**Status:** Complete
**Confidence:** [HIGH]

#### Config Flow

**User Story:** As Darren, I want to set up the integration via the HA UI by entering the bridge URL and token, then selecting which agents to expose, so that setup is guided and validated.

**Acceptance Criteria:**
- [x] Step 1: Enter bridge URL (default: `http://localhost:18780`), bearer token, and an SSL-verify toggle (default on) so a self-signed HTTPS bridge can onboard first-run (CR-0016)
- [x] Step 1 validates connectivity by calling `GET /health`
- [x] Step 1 validates authentication by calling `GET /v1/discovery?include=crew` (requires auth)
- [x] Step 2: Shows discovered agents labelled "name (crew)"; only real, selectable agents listed (no orchestrators, chatbots, workerbots, or bare model passthroughs — CR-0003)
- [x] Step 2: User selects the default agent (used for both chat and voice)
- [x] Config subentry flow adds one conversation agent per bridge agent: cascading crew picker → crew-scoped agent picker → editable per-agent instructions (US0025/CR-0003)
- [x] Subentry reconfigure step edits an existing agent's instructions
- [x] Options flow (CR-0007): Essentials — default agent picker + `ssl_verify`; collapsed Advanced section — the rest
- [x] Options flow: context_max_chars (1000-200000, default 13000)
- [x] Options flow: thinking_timeout (10-3600 seconds, default 120)
- [x] Options flow: session_idle_window as a preset dropdown (Off/5m/30m/2h/8h/24h; default 5 minutes — CR-0013)
- [x] Options flow: enable_streaming (boolean, default false — US0033)
- [x] Options flow: doctor_alerts (boolean, default false — opt-in fleet-doctor repair, CR-0012)
- [x] Config entry stores bridge URL, token, selected agents, and all options; per-agent settings live in subentries

**Dependencies:** Bridge Client
**Status:** Complete
**Confidence:** [HIGH]

#### Data Coordinator

**User Story:** As the integration, I want to periodically poll the bridge for health and agent status so that HA entities stay up to date without overwhelming the bridge.

**Acceptance Criteria:**
- [x] Extends HA's `DataUpdateCoordinator` with configurable poll interval (default 30s)
- [x] Polls `GET /health?depth=shallow` for bridge status and agent counts; enriches with the auth-gated `GET /v1/health` tri-state + `toolSurface`/`readOnlySafe` when available (US0028)
- [x] Polls `GET /v1/discovery?include=crew` for the agent list with capabilities, health, and crew (less frequent, every 5 min)
- [x] Refreshes per-agent usage (`/v1/agents/{id}/usage`) and the fleet-doctor verdict (`/v1/doctor`) on the discovery cadence, best-effort — a failure never fails the poll (CR-0009)
- [x] Caches last-known-good data for first 3 consecutive failures (graceful degradation); usage/doctor carried forward through connectivity outages (BG0007)
- [x] Exposes typed `CoordinatorData`: connected, bridge_status, bridge_version, bridge_uptime, agent counts, agents, last_poll, plus `NotRequired` tool_surface/read_only_safe/usage/doctor
- [x] Accepts validated webhook pushes (status whitelist; typed `agentId`/`healthy` — CR-0014) that bypass the poll cycle
- [x] Triggers entity updates via standard HA coordinator callback

**Dependencies:** Bridge Client
**Status:** Complete
**Confidence:** [HIGH]

#### Conversation Entities

**User Story:** As a voice satellite user, I want to talk to an AI agent via HA Assist so that voice commands are processed by a bridge agent with full awareness of my home's entities and the room I'm in.

**Acceptance Criteria:**
- [x] One `ConversationEntity` per bridge agent, created via config subentries (US0025); an install with no subentries falls back to a single entity for the configured default agent
- [x] Selectable in HA Assist pipeline settings (voice assistants)
- [x] Handles turns via `_async_handle_message` + `ChatLog` (conversation history sourced from `ChatLog`, not a bespoke session store — US0026)
- [x] Builds a layered system prompt: operator-editable per-agent instructions + labelled source block + entity grounding hint + `extra_system_prompt`
- [x] Injects device area (and floor, where available) into the source block for room awareness
- [x] Sends to bridge via `POST /v1/chat/completions` with the entity's `agent` id and a structured `caller_context` envelope (source type, device/satellite, area/floor, unverified account, local time, presence, upcoming, recent changes — US0034)
- [x] Voice-capability gate: only full agents (`agentClass: agent` with a real identity) become voice entities (US0028/CR-0003); entities named "name (crew)" from discovery (BG0005)
- [x] Folds a deny/confirm safety caution into the prompt when exposed entities include safety-relevant domains (lock, alarm, climate, water_heater, cover — US0027)
- [x] Strips a leading `[confirm:LEVEL]` marker from replies, flags the pending confirmation, and keeps the conversation open (US0036)
- [x] Passes `user_input.language` to `IntentResponse` for correct TTS language routing
- [x] Supports all HA-supported languages via `MATCH_ALL` (delegates translation to the AI model)
- [x] Fires `agent_bridge_message_received` (content preview, agent, model, confirmation state) and `agent_bridge_actuation_audit` per reactive turn

**Dependencies:** Bridge Client, Entity Exposure
**Status:** Complete
**Confidence:** [HIGH]

#### Entity Exposure

**User Story:** As an AI agent receiving a voice command, I want to know what devices exist in the home, their current state, and which room they're in, so that I can accurately control the home.

**Acceptance Criteria:**
- [x] Uses HA's native entity exposure settings (Settings > Voice assistants > Expose)
- [x] Formats exposed entities with: entity_id, friendly_name, state, area, and relevant attributes
- [x] Relevant attributes include: brightness, colour_temp, temperature, target_temperature, volume, battery_level, media_title
- [x] Caps at 250 entities per prompt
- [x] Context string truncated at `context_max_chars` (always truncate; the `context_strategy` option was removed by CR-0006)
- [x] Context built fresh per request (not cached) to reflect current state
- [x] Fail-closed: the context is a grounding **hint** for the agent, not state authority — the agent reads live HA state via its own mount before acting (US0027)
- [x] Recent state changes among exposed entities summarised into the caller context (US0034)
- [x] Uses the conversation agent's entity exposure settings from HA's Voice Assistants configuration (Settings > Voice assistants > Expose)

**Dependencies:** None (HA framework)
**Status:** Complete
**Confidence:** [HIGH]

#### Room Awareness

**User Story:** As a voice satellite user, I want the agent to know which room my command came from so that "turn on the lights" means the lights in my room, not the whole house.

**Acceptance Criteria:**
- [x] Extracts device area (and floor, where the floor registry is available) from `ConversationInput.device_id` via the HA device/area registries
- [x] Also handles `ConversationInput.satellite_id` (HA 2025+) for multi-mic arrays where satellite_id differs from device_id (satellite takes priority)
- [x] Renders location into the labelled source block, e.g. `Source: voice via "Kitchen satellite" (Kitchen, Ground floor)`, and into `caller_context.area`/`floor`
- [x] When no device area available (e.g. text input, unassigned device), omits room context (does not guess)
- [x] Source block appears before the entity list in the system prompt

**Dependencies:** Conversation Entities
**Status:** Complete
**Confidence:** [HIGH]

#### Agent-Side Actuation (Option A)

**User Story:** As a voice satellite user, I want the agent to actually control my home (turn on lights, set thermostats, lock doors) when I ask, not just describe what it would do.

The agent actuates Home Assistant through its **own `/api/mcp` mount** (HA's MCP Server integration) — the refined Option A from the US0021 spike. This integration forwards the utterance plus grounding/exposure context and fires `agent_bridge_actuation_audit` (`EVENT_ACTUATION_AUDIT`) once per reactive turn; it does **not** run an HA-side tool loop, parse `tool_calls`, or call `hass.services.async_call()` on the agent's behalf (see `AGENTS.md` Critical Rule 4). The earlier HA-side tool-execution design (v0.1, ADR-005) was removed by EP0007/CR-0006.

**Acceptance Criteria:**
- [x] The reactive turn forwards free text (utterance + grounding hint + `caller_context`) to the bridge agent; the agent reads and controls HA via its own `/api/mcp` mount (US0027/US0031)
- [x] No HA-side tool executor exists; the integration never executes agent-originated service calls
- [x] Entity exposure is fail-closed: the grounding hint only lists entities exposed in HA's Voice Assistants settings (US0027/AC4)
- [x] The grounding prompt folds in a safety caution when exposed entities include deny/confirm domains (lock, alarm_control_panel, climate, water_heater, cover)
- [x] Safety-relevant actions use the confirm-before-actuate contract: the agent prefixes its yes/no question with `[confirm:LEVEL]`; HA strips the marker (including mid-stream — BG0012), surfaces the severity, and keeps the conversation open (US0036)
- [x] `agent_bridge_actuation_audit` fires per reactive turn with agent, conversation id, area, source type, account verification, exposed risky domains, reply preview, and confirmation state (US0027/AC3)

**Dependencies:** Conversation Entities, Entity Exposure, HA MCP Server integration (agent side)
**Status:** Complete
**Confidence:** [HIGH]

#### Bridge Health Sensors

**User Story:** As Darren, I want HA sensors showing bridge health, connectivity, and agent count so that I can build dashboards and trigger automations when the bridge degrades.

**Acceptance Criteria:**
- [x] Bridge Status sensor -- bridge health status (ok, warning, error — the `/v1/health` tri-state mapped per US0028) with version, uptime, `tool_surface`, and `read_only_safe` as attributes
- [x] Bridge Connected binary sensor -- bridge connectivity (on/off, connectivity device class)
- [x] Agent Count sensor -- number of healthy agents with total as attribute
- [x] All sensors update via DataUpdateCoordinator (no independent polling)
- [x] Bridge-level sensors link to a single "Agent Bridge" device in HA device registry

**Dependencies:** Data Coordinator
**Status:** Complete
**Confidence:** [HIGH]

#### Event Entities

**User Story:** As an automation builder, I want HA events fired when agents respond so that I can trigger automations based on agent activity.

**Acceptance Criteria:**
- [x] A Message Received event entity fires on agent response with: agent_id, model, content_preview (the bus event additionally carries `awaiting_confirmation`/`severity`)
- [x] Bus events for automation triggers: `agent_bridge_message_received`, `agent_bridge_actuation_audit` (per reactive turn), `agent_bridge_agent_discovered`/`_removed`, `agent_bridge_bridge_upgraded`
- [x] The event entity is visible in the automation trigger UI

**Dependencies:** Conversation Entities
**Status:** Complete
**Confidence:** [HIGH]

#### Services

**User Story:** As an automation builder, I want HA services to send messages to specific agents and invoke tools so that I can build agent-powered automations.

**Acceptance Criteria:**
- [x] `agent_bridge.send_message` service with fields: message (required), agent_id (optional, falls back to the configured default agent — CR-0016), session_id (optional, passed through as the bridge channel)
- [x] `agent_bridge.invoke_tool` service with fields: agent_id (required), tool_name (required), args (optional object) — a direct, operator-facing call to `POST /v1/tools/invoke`, separate from the conversation loop
- [x] `agent_bridge.ask_with_image` service: snapshots a camera entity and sends it to an agent as a base64 attachment (US0035); same default-agent fallback as send_message
- [x] `agent_bridge.announce` service: proactively speaks a message on an `assist_satellite` target with priority handling — unavailable satellites are skipped unless critical (US0037)
- [x] Services return response data accessible in automation `response_variable`
- [x] Services validate an explicit agent_id against the coordinator's cached agent list; misconfiguration raises `ServiceValidationError` (user-input problem, not an internal error — CR-0016)

**Dependencies:** Bridge Client, Data Coordinator
**Status:** Complete
**Confidence:** [HIGH]

#### Per-Agent Conversation Agents

**User Story:** As Darren, I want each bridge agent to appear as a separate conversation agent in HA so that I can assign Cora to the kitchen satellite and Claude to the study satellite.

**Acceptance Criteria:**
- [x] Each bridge agent added as a `conversation` config subentry gets a conversation agent entity (US0025); the old `enable_per_agent_entities` flag was removed (CR-0006)
- [x] Entities are named "name (crew)" from discovery, never the raw agent id (BG0005)
- [x] Each agent's conversation entity uses the same entity exposure and room awareness logic
- [x] Per-agent conversation agents route via `agent` field in chat request (not bridge default)
- [x] Only voice-capable full agents become entities; orchestrators, chatbots, workerbots, and bare model passthroughs are skipped (US0028/CR-0003)
- [x] Each subentry carries operator-editable per-agent instructions folded into the system prompt (CR-0003)

**Dependencies:** Conversation Entities, Dynamic Agent Discovery
**Status:** Complete
**Confidence:** [HIGH]

#### Dynamic Agent Discovery

**User Story:** As the integration, I want to detect when agents are added or removed from the bridge so that HA stays in sync without manual reconfiguration.

**Acceptance Criteria:**
- [x] Compares current discovery response against previous on each discovery cycle
- [x] Discovery requests `?include=crew` so per-agent crew membership is available for pickers and entity naming (CR-0003/BG0005)
- [x] Emits HA events `agent_bridge_agent_discovered` and `agent_bridge_agent_removed`
- [x] Roster-change webhook events (`agent:registered`/`unregistered`/`updated`) trigger an immediate refresh rather than waiting for the poll
- [x] Entity creation itself is operator-driven via config subentries (auto-churn avoided by design)

**Dependencies:** Data Coordinator
**Status:** Complete
**Confidence:** [HIGH]

#### Webhook Integration

**User Story:** As the integration, I want real-time bridge events via webhooks so that HA reacts instantly to agent outages instead of waiting for the next poll.

**Acceptance Criteria:**
- [x] On setup, registers an HA webhook and subscribes the bridge to the event catalogue (`agent:registered/unregistered/updated`, `agent:health-changed`, `message:sent/error`, `bridge:upgraded`) via `POST /v1/webhooks`
- [x] The HA webhook id is generated once and persisted in the config entry (`CONF_WEBHOOK_ID`) so restarts reuse it — no bridge-subscription churn (CR-0014)
- [x] Webhook registration is local-only and POST-only; the id is the credential and is logged at DEBUG only (CR-0014)
- [x] Pushed data is validated before it reaches sensor state: bridge-status pushes must match the known health vocabulary; per-agent pushes require typed `agentId` (str) + `healthy` (bool) (CR-0014)
- [x] A stale bridge subscription leaked by an unclean shutdown is cleaned up before registering the fresh one (persisted `webhook_subscription_id` — CR-0014)
- [x] `agent:health-changed` pushes update coordinator data immediately; `bridge:upgraded` fires `agent_bridge_bridge_upgraded` for the drift check
- [x] Falls back to polling if webhook registration fails (graceful degradation)
- [x] Unregisters the webhook from both HA and the bridge on integration unload

**Dependencies:** Data Coordinator, Bridge Client
**Status:** Complete
**Confidence:** [HIGH]

#### Broadcast Service

**User Story:** As an automation builder, I want to send a message to all agents (or a tagged subset) in one service call so that system-wide instructions don't need per-agent automations.

**Acceptance Criteria:**
- [x] `agent_bridge.broadcast` service with fields: message (required), tags (optional list; defaults to `['operator']` — the v4.36 bridge rejects tagless broadcasts)
- [x] Calls `POST /v1/broadcast` on the bridge with the `messages[]` + `tags` body
- [x] Normalises the bridge's `responses` object (keyed by agentId) into a stable list with `agent_id` folded in
- [x] Individual agent failures reported in response without blocking others

**Dependencies:** Bridge Client, Services
**Status:** Complete
**Confidence:** [HIGH]

#### SSE Streaming

**User Story:** As a voice satellite user, I want agent responses to stream so that I hear the first words sooner rather than waiting for the complete response.

**Acceptance Criteria:**
- [x] Bridge client supports SSE streaming in the v4.36 shape (`event:message` / `data:{"text":...}` frames terminated by `event:done`); the legacy OpenAI delta shape still accepted (US0023)
- [x] Streaming is opt-in via the `enable_streaming` option (default off, pending live validation — US0033)
- [x] Deltas are fed to HA's `ChatLog` delta stream so TTS can start before the reply completes
- [x] A leading `[confirm:LEVEL]` marker is stripped from the delta stream **before** any content reaches TTS or the stored turn, with the severity surfaced to the confirm handling (BG0012)
- [x] Any streaming failure falls back to the non-streaming path without double-appending the assistant turn
- [x] Streaming timeout 300 seconds (separate from `thinking_timeout`)

**Dependencies:** Bridge Client, Conversation Entities
**Status:** Complete
**Confidence:** [HIGH]

#### Continuation Detection

**User Story:** As a voice satellite user, I want the agent to keep listening when it asks a follow-up question so that multi-turn voice dialogue works naturally.

**Acceptance Criteria:**
- [x] Analyses the agent response for question patterns
- [x] Triggers continuation when: the response ends with `?` AND contains a continuation phrase AND does not end with an exclusion phrase
- [x] Continuation phrases (matched case-insensitively): "would you like", "shall I", "do you want", "should I", "which one", "what would you prefer"
- [x] Exclusion list (suppress continuation): "right?", "isn't it?", "okay?", "yeah?", "let me know if you need anything"
- [x] Both lists are fixed constants (`const.py`); no per-install option
- [x] Returns `continue_conversation: True` in ConversationResult on continuation OR when a `[confirm:LEVEL]` confirmation is pending (US0036)

**Dependencies:** Conversation Entities
**Status:** Complete
**Confidence:** [HIGH]

#### Session Continuity

**User Story:** As a voice satellite user, I want consecutive related turns to share conversation context so that the agent remembers what we were just discussing — without one session accumulating all day.

The v0.1 HA-Store session persistence (`.storage/agent_bridge.sessions`) was retired by EP0007/US0032: the **bridge** persists conversation context per channel (24h TTL), so HA only needs to send a stable channel key and rotate it after an idle gap.

**Acceptance Criteria:**
- [x] Channel key format `ha:{agent_id}:{scope}:{epoch}`, where scope is device → user → default (per-satellite / per-speaker sessions)
- [x] Consecutive turns from the same scope within the `session_idle_window` reuse the same epoch (same bridge session); a longer gap — or a backwards clock jump — mints a new epoch (US0032)
- [x] Idle window configurable as a preset dropdown: Off, 5 minutes (default), 30 minutes, 2 hours, 8 hours, 24 hours (CR-0013)
- [x] Stale scope entries pruned after the bridge's 24h session TTL (bounded memory)
- [x] Channel key sent to bridge as the `channel` field; the bridge manages conversation history
- [x] Service callers (`send_message`, `ask_with_image`) pass their own `session_id` straight through for explicit, stable session control

**Dependencies:** Conversation Entities
**Status:** Complete
**Confidence:** [HIGH]

#### Voice Debug Logging

**User Story:** As Darren debugging voice routing issues, I want detailed logs showing which agent handled a voice request, what channel was used, and what room context was detected.

**Acceptance Criteria:**
- [x] Each conversation turn logs: resolved agent ID, conversation id, session channel, area name, and source type
- [x] Log level is `debug`, captured via HA's built-in per-entry debug logging — the bespoke `debug_logging` option was removed (CR-0013)
- [x] Sensitive data (token, full prompt) never logged

**Dependencies:** Conversation Entities
**Status:** Complete
**Confidence:** [HIGH]

#### Usage & Cost Sensors

**User Story:** As Darren, I want per-agent token and cost sensors in HA so that I can see what the fleet is costing and trigger automations on runaway usage.

**Acceptance Criteria:**
- [x] For each configured voice-capable agent: a "Tokens used" sensor (total in + out over the reported range) and an "Estimated cost" sensor (GBP, monetary device class), attached to the agent's existing device (CR-0009)
- [x] Data sourced from `GET /v1/agents/{id}/usage`, refreshed on the discovery cadence (every 5 min), best-effort per agent — one agent's failure keeps the others' last-known values
- [x] Tokens sensor attributes: input_tokens, output_tokens, turns, per_model breakdown, and the reported range
- [x] Sensors return `None` (not 0) when the bridge sent no usable totals or has no pricing configured; null/non-numeric fields never raise (BG0006)
- [x] Usage carried forward through connectivity outages so sensors do not blank (BG0007); coordinator emits copies so consumers cannot mutate its state (BG0008)

**Dependencies:** Data Coordinator, Bridge Client
**Status:** Complete
**Confidence:** [HIGH]

#### Fleet-Doctor Diagnostics & Repair

**User Story:** As Darren, I want the bridge's one-call fleet diagnosis surfaced in HA so that a genuinely broken fleet raises a repair issue I cannot miss — without benign warnings nagging me.

**Acceptance Criteria:**
- [x] The coordinator fetches `GET /v1/doctor` on the discovery cadence and carries the verdict payload in coordinator data (CR-0009)
- [x] A repair issue is raised only on a `CRITICAL` verdict; `WARNING` is advisory and stays in the diagnostics download (BG0011)
- [x] The repair issue is **opt-in** via the `doctor_alerts` option (default off); disabling the toggle clears any existing issue (CR-0012)
- [x] The issue summarises up to five findings (`area: detail`) and is cleared automatically when the verdict recovers
- [x] The issue registry is only touched when the applied verdict changes (no churn on every poll — BG0007)
- [x] Doctor data carried forward through connectivity outages so a transient outage does not clear a genuine CRITICAL (BG0007)

**Dependencies:** Data Coordinator, Bridge Client
**Status:** Complete
**Confidence:** [HIGH]

#### Diagnostics Platform

**User Story:** As Darren (or a support thread), I want a one-click diagnostics download for the integration so that the bridge state, fleet verdict, and usage can be inspected without secrets leaking.

**Acceptance Criteria:**
- [x] Implements HA's config-entry diagnostics (`diagnostics.py`, CR-0009)
- [x] Includes: redacted entry data/options, connectivity, bridge status/version, tool surface, read_only_safe, the full doctor payload, per-agent usage, and a trimmed agent list (id, name, health, crew, deprecated)
- [x] The bridge token is redacted; any orphaned `caller_id` left in stored options from before CR-0013 is redacted too

**Dependencies:** Data Coordinator
**Status:** Complete
**Confidence:** [HIGH]

#### Agent Memory Services

**User Story:** As an automation builder, I want HA services to record facts into an agent's memory and recall them so that automations can teach agents about the home and query what they know.

**Acceptance Criteria:**
- [x] `agent_bridge.memory_record` service with fields: content (required), agent_id (optional), tags (optional list) — calls `POST /v1/agents/{id}/memory` (CR-0010)
- [x] `agent_bridge.memory_recall` service with fields: query (optional, passed as `?q=` best-effort), agent_id (optional) — calls `GET /v1/agents/{id}/memory` and returns the `items` list
- [x] Both services fall back to the configured default agent when agent_id is omitted; a missing default returns a clean error in the response
- [x] An explicit agent_id is validated against the coordinator's cached agent list
- [x] Bridge errors are returned in the service response (`error` field), not raised as stack traces

**Dependencies:** Bridge Client, Data Coordinator
**Status:** Complete
**Confidence:** [HIGH]

#### AI Tasks

**User Story:** As an automation builder, I want to ask an agent for structured data (`ai_task.generate_data`) so that dashboards and templates can consume agent output as JSON, not prose.

**Acceptance Criteria:**
- [x] One `ai_task` entity per configured voice-capable bridge agent, on the agent's existing device (US0039)
- [x] Supports `GENERATE_DATA`; when a structure is requested, instructs the agent to reply with JSON only and strips a stray code fence before parsing
- [x] Invalid JSON for a structured request raises a clear `HomeAssistantError`
- [x] Reuses the same bridge client and ChatLog-to-messages conversion as the conversation entity

**Dependencies:** Bridge Client, Conversation Entities
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
- Entity exposure respects HA's native expose settings -- the integration does not override user choices
- Voice/AI-task entities are only created for full agents per the v4.x taxonomy (`agentClass: agent`, real identity substrate, not an orchestrator — US0028/CR-0003)
- Services fall back to the configured default agent when `agent_id` is omitted; an explicit unknown agent raises `ServiceValidationError` (CR-0016)

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
- **System prompt:** Layered — per-agent instructions (operator-editable, CR-0003) + labelled `[home-assistant-source]` block + entity grounding hint + `extra_system_prompt` (+ safety caution when risky domains are exposed)
- **Entity context format:** One line per entity: `{friendly_name} ({entity_id}): {state} [area: {area}] [brightness: {brightness}]`
- **Room awareness:** Rendered into the source block, e.g. `Source: voice via "Kitchen satellite" (Kitchen, Ground floor)`
- **No model-specific tuning:** The bridge and agents handle prompt engineering

### Context Management
- Entity context rebuilt per request (stateless)
- Conversation history managed by bridge channels (not by the integration)
- Context truncation at configurable max_chars to prevent prompt overflow

---

## 7. Data Architecture

### Data Models

**Config Entry Data (entry.data):**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| bridge_url | string | Yes | - | Bridge base URL (e.g. http://10.0.0.206:18780) |
| bridge_token | string | Yes | - | Bearer token for bridge auth |
| default_agent | string | Yes | - | Agent ID for default routing (also the `x-bridge-mcp-caller` identity — BG0004) |
| voice_agent | string | Yes | default_agent | Kept equal to default_agent by the flows |
| webhook_id | string | No | generated | Persistent HA webhook id (CR-0014) |
| webhook_subscription_id | string | No | - | Last bridge subscription id, for stale-subscription cleanup (CR-0014) |

**Config Entry Options (entry.options):**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| context_max_chars | int | No | 13000 | Max entity context length (always truncate) |
| thinking_timeout | int | No | 120 | Timeout for agent response in seconds |
| ssl_verify | bool | No | true | Verify SSL certificates (also offered first-run — CR-0016) |
| session_idle_window | int | No | 300 | Idle gap (seconds) that rotates the session channel; preset dropdown (CR-0013) |
| enable_streaming | bool | No | false | Stream replies to TTS as deltas (US0033) |
| doctor_alerts | bool | No | false | Opt-in fleet-doctor repair issue (CR-0012) |

**Conversation Subentry Data (one per agent — US0025/CR-0003):**

| Field | Type | Description |
|-------|------|-------------|
| agent_id | string | Bridge agent id |
| crew | string | Crew the agent belongs to (from `?include=crew`) |
| prompt | string | Operator-editable instructions folded into the system prompt |

**Coordinator Data:**

| Field | Type | Description |
|-------|------|-------------|
| connected | bool | Bridge reachable |
| bridge_status | string | ok, warning, error (tri-state mapped — US0028) |
| bridge_version | string | Bridge software version |
| bridge_uptime | int | Seconds since bridge start |
| agent_count_healthy | int | Healthy agent count |
| agent_count_total | int | Total agent count |
| agents | list[AgentInfo] | Per-agent details from discovery |
| last_poll | string | Last successful poll (ISO timestamp) |
| tool_surface | string (NotRequired) | `/v1/health` toolSurface — actuation diagnostics |
| read_only_safe | bool (NotRequired) | `/v1/health` readOnlySafe |
| usage | dict (NotRequired) | AgentUsageSummary keyed by agent_id (CR-0009) |
| doctor | dict (NotRequired) | Fleet-doctor verdict payload (CR-0009) |

**AgentInfo (v4.x discovery surface, US0028):**

| Field | Type | Description |
|-------|------|-------------|
| id / name / description | string | Identity |
| healthy | bool | Derived: state ready/healthy AND circuit closed |
| adapter | string | Adapter type (http-openai, cli, etc.) |
| capabilities | dict | Agent capabilities (chat, tools, streaming) |
| tags | list[string] | Agent tags |
| health_state / circuit / inflight / last_seen_at / stale_after | mixed | CR-0097 health block |
| latency_ms / requests / errors | number | CR-0245 metrics |
| agent_class / identity_substrate / capability_envelope / is_orchestrator / framework | mixed | v4.x taxonomy (voice-capability gating) |
| effective_model / model_provider / deprecated | mixed | Model + lifecycle |
| crew | string | Crew membership (from `?include=crew`) |

**AgentUsageSummary (per agent, from `GET /v1/agents/{id}/usage` — CR-0009):**

| Field | Type | Description |
|-------|------|-------------|
| totals.totalIn | int | Input tokens over the reported range |
| totals.totalOut | int | Output tokens over the reported range |
| totals.turnCount | int | Conversation turns |
| estimatedTotalCostGBP | float | Estimated cost; absent/null when the bridge has no pricing |
| perModel | list | Per-model breakdown |
| perChannel | list | Per-channel breakdown |
| range | object | The period the totals cover |

**Doctor Verdict (from `GET /v1/doctor` — CR-0009):**

| Field | Type | Description |
|-------|------|-------------|
| verdict | string | HEALTHY, WARNING, or CRITICAL |
| summary | string | One-line fleet diagnosis |
| findings | list | Items with severity / area / detail |
| recommendations | list | Suggested operator actions |

**Memory Item (from `GET /v1/agents/{id}/memory` — CR-0010):**

| Field | Type | Description |
|-------|------|-------------|
| agent | string | Owning agent id (response envelope) |
| items | list | Recorded memory items; each carries the recorded `content` (+ optional `tags`) |

**Session Channel (in-memory, US0032):**

| Field | Type | Description |
|-------|------|-------------|
| _session_epochs | dict[str, (int, datetime)] | Per-scope epoch + last-turn time, per conversation entity |

Channel key format: `ha:{agent_id}:{scope}:{epoch}` (e.g. `ha:cora:dev:abc123:2`); scope is `dev:{device_id}` → `usr:{user_id}` → `default`.

### Storage Mechanisms
- Config entry: HA's built-in encrypted storage (`.storage/`)
- Session channel epochs: in-memory per entity (the **bridge** persists conversation context per channel, 24h TTL — the v0.1 HA Store at `.storage/agent_bridge.sessions` was retired by US0032)
- Coordinator state: in-memory only (rebuilt from bridge on each poll)
- Conversation history: HA-side per-conversation history via `ChatLog`; cross-turn agent context delegated to bridge channels
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
| ssl_verify | Config flow + options flow | true | Verify bridge SSL certificates (CR-0016 added the first-run toggle) |
| enable_streaming | Options flow (Advanced) | false | Stream agent replies to TTS as deltas (US0033) |
| doctor_alerts | Options flow (Advanced) | false | Opt-in fleet-doctor repair issue on CRITICAL (CR-0012) |

---

## 10. Quality Assessment

### Tested Functionality
A full pytest suite (unit + integration, mocked bridge) covers every shipped feature, including the CR-0009/CR-0010 observability + memory features, the CR-0014 webhook-hardening and BG0012 streaming regressions, and an OpenAPI contract check against a captured bridge spec. CI (`.github/workflows/validate.yml`) runs ruff + pytest against the pinned HA 2026.2.3 / Python 3.13, plus hassfest and HACS validation. See TSD.

### Untested Areas
Live-bridge and voice-satellite paths are manual E2E only (by design — unit tests never hit a live bridge).

### Technical Debt
- E2E feature matrix in the TSD is executed manually per release, not automated

---

## 11. Open Questions

- [x] **Q:** Should the integration register a webhook with the bridge on setup, or is polling sufficient for homelab scale?
  **Context:** Webhooks give real-time health updates but add complexity (HA needs a reachable callback URL). Polling at 30s is probably fine for homelab.
  **Decision:** Polling only in Phase 1 (EP0001-EP0004). Webhook Integration deferred to EP0005 (P2). See ADR-002 in TRD.

- [x] **Q:** Should per-agent conversation entities be dynamic (auto-created from discovery) or user-selected in config flow?
  **Context:** Dynamic is more automated but creates entity churn if agents come and go. User-selected is more controlled. Current design has tension: `enable_per_agent_entities` gates creation (user-controlled), but Dynamic Agent Discovery AC says entities auto-update within one poll cycle (implies fully dynamic once enabled).
  **Decision:** Hybrid -- user enables the feature via `enable_per_agent_entities` flag, then all discovered agents with `chat: true` get entities automatically. Discovery drives the list, the flag is the on/off switch. Implemented in conversation.py and binary_sensor.py. *(Superseded by US0025/CR-0003: the flag is gone; the operator now adds each agent explicitly as a config subentry — fully user-selected, no entity churn.)*

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
| 2026-06-09 | 0.10.0 | RV0006 release-gate review: marked HA Service Execution + Tool Invoked event + the removed options as superseded by Option A / CR-0006 (agent actuates via its own `/api/mcp` mount); added Usage & Cost Sensors (CR-0009) and Agent Memory Services (CR-0010) to the feature inventory. Shipped this release: CR-0006 (dead-code cull), CR-0007 (options UX), CR-0008 (bridge v4.141 re-baseline), CR-0009, CR-0010, BG0005 (entity naming). Full §3/§7 feature-detail + TRD/TSD expansion tracked in CR-0011. |
| 2026-07-04 | 0.11.1 | CR-0011 full reconcile to shipped code (bridge v4.141.0 / HA 2026.2.3 baseline): rewrote the superseded HA Service Execution section as Agent-Side Actuation (Option A); rewrote Session Persistence as idle-windowed Session Continuity (US0032/CR-0013); added feature details + ACs for Usage & Cost Sensors, Fleet-Doctor Diagnostics & Repair, Diagnostics Platform, Agent Memory Services (CR-0009/CR-0010) and AI Tasks (US0039); added AgentUsageSummary / doctor-verdict / memory-item data models; refreshed config-entry/options/subentry and coordinator data models; folded in the SPRINT-2026-07-04 deltas (CR-0014 webhook hardening, CR-0015 URL-encoding, CR-0016 service semantics + first-run SSL toggle, BG0012 streaming confirm-marker strip). |

---

> **Confidence Markers:** [HIGH] clear requirements | [MEDIUM] inferred from patterns | [LOW] speculative
>
> **Status Values:** Complete | Partial | Stubbed | Broken | Not Started
