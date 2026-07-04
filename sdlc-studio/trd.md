# Technical Requirements Document

**Project:** Agent Bridge HA
**Version:** 0.11.1
**Status:** Current
**Last Updated:** 2026-07-04
**Last Review:** 2026-07-04 — CR-0011 full reconcile against the shipped integration
**PRD Reference:** [PRD](prd.md)

> **Currency note (CR-0011, 2026-07-04).** This TRD was fully reconciled against the
> shipped code (0.11.x on this branch; tested baseline **bridge v4.141.0 / HA 2026.2.3**,
> per `const.TESTED_*`). The interfaces, endpoints, data models, module tables, and repo
> structure below describe **reality as shipped**: the `ConversationEntity`/`ChatLog`
> design with agent-side actuation (Option A — see **ADR-006**, which supersedes ADR-005),
> the CR-0009/CR-0010 client methods, the CR-0014 hardened webhook lifecycle, and CR-0015
> URL-encoded path parameters. The superseded v0.1 tool-execution design lives in git
> history and in the retained (superseded) ADR-005 record. The 2026-06-01 audit that
> triggered the redesign is [CR-0002](change-requests/cr0002.md) /
> [EP0007](epics/EP0007-bridge-v436-modern-ha-realignment.md).

---

## 1. Executive Summary

### Purpose
Define the technical architecture for Agent Bridge HA -- a Home Assistant custom component that exposes Agent Bridge agents as native HA conversation agents with entity exposure, room awareness, health monitoring, and automation events.

### Scope
- Async HTTP client for the Agent Bridge REST API (chat, streaming, discovery, health, usage, doctor, memory, agent-context, webhooks)
- HA config flow with bridge discovery, agent selection, and per-agent conversation subentries
- DataUpdateCoordinator for bridge health/discovery/usage/doctor polling
- One `ConversationEntity` per bridge agent (config subentries) plus per-agent `ai_task` entities
- Entity exposure system (HA entity state formatted as an AI grounding hint)
- Room/area awareness and structured `caller_context` for voice requests
- Agent-side actuation boundary (Option A): the agent controls the home via its own `/api/mcp` mount; HA emits a per-turn audit event (ADR-006)
- Sensor, binary_sensor, event, and diagnostics platforms
- HA services for message sending, tool invocation, broadcast, camera-image asks, announcements, and agent memory
- Hardened webhook subscription for real-time bridge events (CR-0014) and bridge-drift defences (US0029)
- HACS distribution

### Key Decisions
- Thin adapter: all routing, resilience, and agent management delegated to the bridge
- No new pip dependencies beyond what HA bundles (aiohttp, voluptuous)
- Per-agent entities created via config subentries (operator-driven, US0025)
- Entity exposure cherry-picked from OpenClaw fork patterns (proven in production), reframed as a fail-closed grounding hint
- Cross-turn agent context managed by bridge channels (idle-windowed keys, US0032); per-conversation history via HA's `ChatLog`
- Actuation is agent-owned via `/api/mcp` — no HA-side tool loop (ADR-006)
- Polling plus a hardened webhook subscription for real-time events (CR-0014)

---

## 2. Project Classification

**Project Type:** custom_component (Home Assistant integration)

**Classification Rationale:** This is a platform adapter that runs inside Home Assistant's Python runtime. It is not a standalone API backend, CLI tool, or library. It follows HA's integration patterns (config flow, entity platforms, coordinator).

**Architecture Implications:**
- **Default Pattern:** HA custom component (config flow + entity platforms + coordinator)
- **Pattern Used:** HA custom component with bridge-side intelligence
- **Deviation Rationale:** None -- standard HA custom component pattern is correct

---

## 3. Architecture Overview

### System Context

```
┌─────────────────────────────────────────────────┐
│                 Home Assistant                     │
│                                                    │
│  ┌──────────────┐    ┌────────────────────────┐   │
│  │ Voice        │    │ custom_components/       │   │
│  │ Satellites   │───►│ agent_bridge/            │   │
│  │ (Assist)     │    │                          │   │
│  └──────────────┘    │  ┌────────────────────┐  │   │
│                       │  │ Conversation Agent │  │   │
│  ┌──────────────┐    │  │ (per bridge agent)  │  │   │
│  │ Automations  │───►│  ├────────────────────┤  │   │
│  │ & Scripts    │    │  │ Entity Exposure     │  │   │
│  └──────────────┘    │  ├────────────────────┤  │   │
│                       │  │ Bridge Client      │──┼───┼──► Agent Bridge (:18780)
│  ┌──────────────┐    │  ├────────────────────┤  │   │        │
│  │ Dashboards   │◄───│  │ Coordinator        │  │   │    ┌───┴───────┐
│  │ (Sensors)    │    │  ├────────────────────┤  │   │    │ Cora      │
│  └──────────────┘    │  │ Sensors / Events   │  │   │    │ Claude    │
│                       │  └────────────────────┘  │   │    │ Prof      │
│  ┌──────────────┐    └────────────────────────┘   │    │ Knox      │
│  │ Entity       │                                  │    │ Quill     │
│  │ Registry     │◄── Entity Exposure reads from    │    │ ...       │
│  └──────────────┘                                  │    └───────────┘
└─────────────────────────────────────────────────┘
```

### Architecture Pattern
HA custom component (thin adapter with coordinator pattern).

**Rationale:** HA mandates this pattern for integrations. The component registers entities, polls for data, and responds to platform events. All complex logic (agent routing, failover, circuit breaking) lives in the Agent Bridge -- the HA component is intentionally simple.

### Component Overview

| Component | Responsibility | Technology |
|-----------|---------------|------------|
| Bridge Client (`client.py`) | HTTP communication with Agent Bridge REST API; typed errors; URL-encoded path parameters (CR-0015) | aiohttp (HA shared session) |
| Config Flow (`config_flow.py`) | UI-driven setup (first-run SSL toggle, CR-0016), options (Essentials + Advanced, CR-0007), and conversation subentries (crew → agent → instructions, CR-0003) | HA ConfigFlow/ConfigSubentryFlow, voluptuous |
| Data Coordinator (`coordinator.py`) | Periodic bridge health/discovery polling; usage + doctor refresh on the discovery cadence; validated webhook pushes (CR-0014) | HA DataUpdateCoordinator |
| Conversation Entity (`conversation.py`) | HA Assist front-end, one per agent (config subentries); free-text forward + grounding hint + `caller_context` via `_async_handle_message`/`ChatLog`; confirm-marker handling (US0036/BG0012); actuation audit event | HA `ConversationEntity` (EP0007) |
| AI Task Platform (`ai_task.py`) | One `ai_task` entity per agent for `generate_data` (structured JSON / summaries, US0039) | HA `AITaskEntity` |
| Entity Exposure (`exposure.py`) | Format HA entity state as a grounding **hint** for the agent (fail-closed); recent-changes summary (US0034) | HA entity/device/area registries |
| Drift Defences (`drift.py`) | Fetch `/v1/agent-context` on setup + `bridge:upgraded`, raise an HA repair issue past baseline (US0029); opt-in fleet-doctor repair issue on CRITICAL (CR-0009/CR-0012) | HA issue registry |
| Webhook Handler (`webhook.py`) | Persistent local-only/POST-only HA webhook; bridge subscription lifecycle incl. stale-subscription cleanup (CR-0014); event dispatch to coordinator/bus | HA webhook component |
| Diagnostics (`diagnostics.py`) | Redacted config-entry diagnostics download (doctor, usage, agents, tool surface) (CR-0009) | HA diagnostics platform |
| Sensor Platform (`sensor.py`) | Bridge status + agent count sensors; per-agent tokens + estimated-cost sensors (CR-0009) | HA SensorEntity |
| Binary Sensor Platform (`binary_sensor.py`) | Bridge connectivity sensor | HA BinarySensorEntity |
| Event Platform (`event.py`) | Message Received event entity | HA EventEntity |
| Service Handler (`services.py`) | send_message, invoke_tool, broadcast, ask_with_image, announce, memory_record, memory_recall services; default-agent fallback + `ServiceValidationError` (CR-0016) | HA service registry |
| Session Continuity | Idle-windowed bridge channel keys per scope (in `conversation.py`, US0032); the bridge persists per-channel context | Internal (in-memory epochs) |
| Continuation Detector | Analyse agent responses for follow-up question patterns | Internal (in conversation.py) |
| Helpers (`helpers.py`) | Response text extraction, caller-id resolution, agent selectability/crew/label helpers | Internal |

### Reactive vs Proactive Boundary (EP0007 / US0030)

Two **non-overlapping** paths connect Home Assistant and the agent fleet. This
component owns only the first; it documents — but does not implement — the second.

| | Reactive (this component) | Proactive (agent-owned) |
|---|---|---|
| **Trigger** | User speaks to HA Assist | Agent decides to act (autonomy, schedules, peer requests) |
| **Path** | Voice/Assist → `ConversationEntity._async_handle_message` → bridge agent (free text + grounding hint) → reply | Agent → its harness-mounted HA tool surface (`/api/mcp`, the DBee pattern) → HA service call |
| **Who actuates HA** | **The agent**, via its own `/api/mcp` mount — *not* this component | The agent, via the same mount |
| **Tool contract** | None on the bridge (v4.36 carries no `tool_calls`); HA exposure is a **grounding hint**, not authority | HA-MCP tools mounted per harness (US0031) |
| **Audit** | `EVENT_ACTUATION_AUDIT` HA-side hook → bridge audit log (US0031) | Agent emits the authoritative per-actuation audit event from its mount |

**Key consequence (the actuation fix):** because the bridge has no `tool_calls`
contract, the reactive path cannot round-trip HA's LLM-API `llm.Tool` through the
agent. So actuation is delegated to the agent's own HA mount (refined Option A,
US0021). The component is the Assist front-end (voice/picker/room routing +
grounding hint + audit hook); it cedes tool exposure to the `/api/mcp` mount (OQ3).

**Voice metadata (OQ6):** `device_id`/`satellite_id`/`source`/`area`/`language`
reach the agent via **prompt-fold** in the chat `metadata` field on the reactive
turn (no bridge passthrough CR required for the chosen design).

**Per-agent readiness** lives at the auth-gated **`/v1/health`** (tri-state +
`toolSurface`/`readOnlySafe`), never a per-agent `depth` projection on `/health`
(that was a phantom — the handler ignores the query string).

---

## 4. Technology Stack

### Core Technologies

| Category | Technology | Version | Rationale |
|----------|-----------|---------|-----------|
| Language | Python | 3.13 (CI) | HA requirement |
| Framework | Home Assistant Core | 2025.7.0+ (HACS floor); tested pin 2026.2.3 (US0029) | Target platform |
| HTTP Client | aiohttp | (HA bundled) | HA's standard async HTTP, already in runtime |
| Validation | voluptuous | (HA bundled) | HA's standard config validation |

### Build and Development

| Tool | Purpose |
|------|---------|
| ruff | Linting and formatting (HA standard) |
| mypy | Type checking |
| pytest | Unit and integration tests |
| pytest-homeassistant-custom-component | HA test fixtures and mocks |

### Infrastructure Services

| Service | Provider | Purpose |
|---------|----------|---------|
| HACS | Self-hosted (HA addon) | Distribution and updates |
| Agent Bridge | Self-hosted (agentbox02:18780) | Agent communication backend |

---

## 5. API Contracts

### API Style
The integration is a **consumer** of the Agent Bridge REST API, not a provider. It does not expose its own API endpoints (beyond HA's standard entity/service framework).

### Bridge API Endpoints Consumed (client methods)

All endpoints are wrapped by `BridgeClient` methods. Path parameters (agent ids,
subscription ids) are **URL-encoded** before interpolation (`urllib.parse.quote`,
CR-0015), so an id containing `/`, spaces, or unicode cannot break the path.

| Client method | Method | Path | Purpose | Auth |
|---------------|--------|------|---------|------|
| `check_alive()` | `GET` | `/health` | Connectivity check (5s timeout) | No |
| `health(depth)` | `GET` | `/health?depth={shallow\|deep}` | Bridge status + agent counts (polling) | No |
| `agent_health()` | `GET` | `/v1/health` | Per-agent readiness (tri-state `bridge` rollup, `toolSurface`, `readOnlySafe` — US0028) | Yes |
| `discover(include)` | `GET` | `/v1/discovery[?include=crew]` | Agent list with capabilities, health, and crew | Yes |
| `agent_context()` | `GET` | `/v1/agent-context` | Machine-readable changelog (version, capabilities, deprecations) for the drift check (US0029) | Yes |
| `agent_usage(agent_id)` | `GET` | `/v1/agents/{id}/usage` | Per-agent token + cost telemetry (CR-0009) | Yes |
| `doctor()` | `GET` | `/v1/doctor` | One-call fleet diagnosis (CR-0009) | Yes |
| `memory_record(agent_id, content, tags)` | `POST` | `/v1/agents/{id}/memory` | Record a memory item (CR-0010) | Yes |
| `memory_recall(agent_id, query)` | `GET` | `/v1/agents/{id}/memory[?q=]` | Recall memory items; `?q=` is best-effort (CR-0010) | Yes |
| `chat(...)` / `chat_stream(...)` | `POST` | `/v1/chat/completions` | Send message to agent (optionally streaming) | Yes |
| `invoke_tool(agent_id, tool_name, args)` | `POST` | `/v1/tools/invoke` | Invoke agent tool (v4.36 `agent`/`tool` body) | Yes |
| `broadcast(message, tags)` | `POST` | `/v1/broadcast` | Send to multiple agents (`messages[]` + `tags`; tags default `['operator']`) | Yes |
| `register_webhook(url, events)` | `POST` | `/v1/webhooks` | Register event subscription | Yes |
| `unregister_webhook(id)` | `DELETE` | `/v1/webhooks/{id}` | Remove event subscription | Yes |

The consumed set is pinned by a contract test (`tests/test_openapi_contract.py`)
against a captured slice of the bridge's `GET /v1/openapi.json` (CR-0008).

### Crew-Aware Discovery and Agent Naming

`discover(include=["crew"])` requests the v4.36 `?include=crew` projection — the
only place per-agent crew membership is exposed, as a nested
`crew: {team, visibleCrews}` block (CR-0003). The integration uses it in three
places:

- **Pickers** (config flow step 2, options flow, subentry flow): agents are listed
  as `name (crew)` via `helpers.agent_label()`, filtered to real, selectable agents
  by `helpers.is_selectable_agent()` (no orchestrators, chatbots, workerbots, or
  bare model passthroughs).
- **Entity naming** (BG0005): conversation/AI-task/usage entities are named from
  the discovery label, never the raw agent id.
- **Coordinator data**: `AgentInfo.crew` is populated on every discovery poll.

Every request also carries the `x-bridge-mcp-caller` header set to the configured
default agent (a registered agent id — BG0004), so the bridge can resolve the
caller's crew for cross-agent dispatch; a 403 with a caller-identity error code is
surfaced as `BridgeCallerError`, distinct from a bad token.

### Chat Request Format (sent to bridge)

```python
{
    "messages": [
        {"role": "system", "content": "<instructions>\n\n<source_block>\n\n<entity_context>\n\n<extra_system_prompt>"},
        {"role": "user", "content": "<user_message>"}       # plus prior ChatLog turns
    ],
    "agent": "<agent_id>",               # The entity's bridge agent
    "channel": "ha:<agent_id>:<scope>:<epoch>",  # Idle-windowed session channel (US0032)
    "caller_context": {                  # Structured speaker/source/location envelope
        "source_type": "voice",          # "voice" | "text" | "automation"
        "source_system": "home_assistant",
        "language": "en",                # From ConversationInput.language
        "local_time": "2026-07-04 09:30",
        "timezone": "Europe/London",
        "audio_only": True,              # Voice turns only
        "device_id": "<ha_device_id>",   # Voice turns only
        "device_name": "Kitchen satellite",
        "satellite_id": "<ha_sat_id>",   # When it differs from device_id
        "area": "Kitchen",               # Resolved area / floor
        "floor": "Ground floor",
        "account": {"name": "Darren", "verified": False},
        "presence": "home: Darren; away: ...",       # US0034 grounding
        "upcoming": "next alarm 07:00; calendar: ...",
        "recent_changes": "<recent state changes among exposed entities>"
    },
    "attachments": [                      # ask_with_image only (US0035)
        {"id": "ha-camera-camera.front", "mime_type": "image/jpeg",
         "base64": "<...>", "source": {"bot_id": "homeassistant"}}
    ]
}
```

The envelope is also rendered into the system prompt as a labelled
`[home-assistant-source]` block, kept separate from the user utterance so the
agent cannot confuse metadata with intent. Automation-sourced turns instruct the
agent to apply stricter safety gating (no human present).

### Chat Response Format (received from bridge)

```python
{
    "id": "chatcmpl-xxx",
    "object": "chat.completion",
    "created": 1712345678,
    "model": "kimi-k2.5:cloud",
    "agent": "cora",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "I've turned on the kitchen lights."},
            "finish_reason": "stop"
        }
    ],
    "usage": {"input_tokens": 1200, "output_tokens": 45},
    "trace_id": "abc-123"
}
```

### Actuation Flow (Option A — see ADR-006)

There is **no tool-call contract** between HA and the bridge: the reactive path
sends free text and receives free text. Actuation happens on the agent's side,
through the agent's own `/api/mcp` mount into Home Assistant.

```
1. User: "Turn on the kitchen lights"
         │
2. Integration builds the layered system prompt (instructions + source block
   + entity grounding hint [+ safety caution]) and the caller_context envelope
         │
3. POST /v1/chat/completions → Agent Bridge → Agent
         │
4. The AGENT reads live HA state and calls HA services via its own /api/mcp
   mount (HA's MCP Server integration) — not via this component
         │
5. Agent replies with the spoken confirmation ("Done — the kitchen lights
   are on."), optionally prefixed [confirm:LEVEL] for safety-relevant asks
         │
6. Integration strips any confirm marker, fires agent_bridge_message_received
   and agent_bridge_actuation_audit, and returns ConversationResult
```

**Confirm-before-actuate contract (US0036):** for safety-relevant domains the
grounding prompt instructs the agent to ask a yes/no question first, prefixed
`[confirm:high]` (or `normal`/`low`). HA strips the marker from the spoken text —
including mid-stream, before any delta reaches TTS or the stored `ChatLog` turn
(BG0012) — surfaces the severity on the events, and keeps the conversation open
for the answer.

### SSE Streaming

The bridge client supports optional Server-Sent Events streaming for chat completions (opt-in via the `enable_streaming` option, US0033):

```python
# Stream request (chat_stream() adds stream=True to the chat request)
{
    "messages": [...],
    "agent": "cora",
    "channel": "<session_channel>",
    "caller_context": {...},
    "stream": True
}

# v4.36 SSE frames (text/event-stream) -- US0023
event: message
data: {"text": "I've"}

event: message
data: {"text": " turned"}

event: done
```

**Client behaviour:**
- `chat_stream()` returns an async iterator of content delta strings
- Parses the v4.36 `event:message` / `data:{"text":...}` frames, terminated by `event:done` (or `{"done": true}`); the legacy OpenAI `choices[].delta.content` + `data:[DONE]` shape is still accepted for backward compatibility
- The conversation entity adapts deltas to HA's `AssistantContentDeltaDict` stream and feeds `ChatLog.async_add_delta_content_stream` so TTS can start early; a leading `[confirm:LEVEL]` marker is stripped from the head of the stream before any content is emitted (BG0012)
- On any streaming failure, falls back to the non-streaming path without double-appending the assistant turn
- Streaming timeout 300 seconds (separate from `thinking_timeout`)

### Health Response Format (shallow)

```python
{
    "status": "ok",           # ok | degraded | error
    "version": "3.2.0",
    "uptime_seconds": 12345,
    "mode": "primary",
    "agents": {"total": 7, "healthy": 6}
}
```

### Health Response Format (deep)

> **Note:** Shallow health returns `agents` as a count object (`{"total": 7, "healthy": 6}`), while deep health returns `agents` as a dict keyed by agent ID. The coordinator must handle both shapes when parsing.

```python
{
    "status": "ok",
    "version": "3.2.0",
    "uptime_seconds": 12345,
    "mode": "primary",
    "agents": {
        "cora": {"status": "healthy", "adapter": "http-openai", "latencyMs": 120},
        "claude": {"status": "unhealthy", "adapter": "cli", "error": "timeout"}
    }
}
```

### Discovery Response Format (`?include=crew`)

```python
{
    "agents": [
        {
            "id": "cora",
            "name": "Cora",
            "description": "Primary AI assistant",
            "status": "healthy",                      # legacy fallback
            "adapter": "http-openai",
            "capabilities": {"chat": true, "tools": ["web_search", "email"], "streaming": true},
            "tags": ["primary", "nlp"],
            "health": {"state": "ready", "circuit": "closed", "inflight": 0,
                       "lastSeenAt": "...", "staleAfter": 90},      # CR-0097 block
            "metrics": {"latency": 120, "requests": 42, "errors": 0},
            "agentClass": "agent",                    # v4.x taxonomy
            "identitySubstrate": "persona",
            "isOrchestrator": false,
            "effectiveModel": "kimi-k2.5:cloud",
            "deprecated": false,
            "crew": {"team": "home", "visibleCrews": ["home", "ops"]}  # include=crew only
        }
    ]
}
```

An agent is `healthy` only when `health.state` is ready/healthy **and** the
circuit is closed (busy/open-circuit/stale agents read distinctly).

### Usage Response Format (`GET /v1/agents/{id}/usage` — CR-0009)

```python
{
    "totals": {"totalIn": 120000, "totalOut": 45000, "turnCount": 87},
    "estimatedTotalCostGBP": 1.23,      # absent/null when no pricing configured
    "perModel": [{"model": "kimi-k2.5:cloud", ...}],
    "perChannel": [{"channel": "ha:cora:dev:abc:1", ...}],
    "range": {"from": "...", "to": "..."}
}
```

### Doctor Response Format (`GET /v1/doctor` — CR-0009)

```python
{
    "verdict": "WARNING",               # HEALTHY | WARNING | CRITICAL
    "summary": "2 agents stale",
    "findings": [{"severity": "warning", "area": "agents", "detail": "..."}],
    "recommendations": ["..."]
}
```

### Memory Response Format (`GET /v1/agents/{id}/memory` — CR-0010)

```python
{"agent": "cora", "items": [{"content": "The loft hatch sticks", "tags": ["house"]}]}
```

### Error Response Format (from bridge)

```python
{
    "error": {
        "code": "AGENT_TIMEOUT",       # String error code
        "message": "Agent cora did not respond within 120s",
        "agent": "cora",
        "retryable": true,
        "suggestedBackoffMs": 5000,
        "traceId": "abc-123"
    }
}
```

### Error Handling Strategy

| Bridge Error Code | HA Behaviour |
|-------------------|-------------|
| `AGENT_TIMEOUT` | Return user-friendly "Agent is taking too long" message |
| `AGENT_UNREACHABLE` | Return "Agent is currently unavailable" |
| `CIRCUIT_OPEN` | Return "Agent is temporarily offline" |
| `NO_CAPABLE_AGENT` | Return "No agent available to handle this request" |
| `AUTH_ERROR` (401/403) | Return "There is an authentication problem with the bridge" |
| `CALLER_ERROR` (403 caller-identity) | Return "The bridge does not recognise this Home Assistant's agent identity" (`BridgeCallerError`, distinct from a bad token — BG0004) |
| `RATE_LIMITED` | Return "Agent is busy, please try again shortly" |
| Connection refused | Mark bridge as disconnected, return "Bridge is offline" |

All error messages are user-friendly for voice output. No stack traces, error codes, or technical jargon in conversation responses.

---

## 6. Data Architecture

### Data Models

#### Config Entry Data (entry.data)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| bridge_url | str | Required, valid URL | Bridge base URL |
| bridge_token | str | Required, non-empty | Bearer token |
| default_agent | str | Required, valid agent ID | Default agent (also the `x-bridge-mcp-caller` identity — BG0004) |
| voice_agent | str | Kept equal to default_agent | Voice agent |
| webhook_id | str | Generated once | Persistent HA webhook id (CR-0014) |
| webhook_subscription_id | str | Optional | Last bridge subscription id, for stale-subscription cleanup (CR-0014) |

#### Config Entry Options (entry.options)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| context_max_chars | int | 1000-200000, default 13000 | Max entity context chars (always truncate) |
| thinking_timeout | int | 10-3600, default 120 | Agent response timeout (seconds) |
| ssl_verify | bool | default true | SSL certificate verification (also first-run — CR-0016) |
| session_idle_window | int | preset set {0, 300, 1800, 7200, 28800, 86400}, default 300 | Idle gap that rotates the session channel key (US0032/CR-0013) |
| enable_streaming | bool | default false | Stream replies to TTS as deltas (US0033) |
| doctor_alerts | bool | default false | Opt-in fleet-doctor repair issue (CR-0012) |

#### Conversation Subentry Data (one per agent — US0025)

| Field | Type | Description |
|-------|------|-------------|
| agent_id | str | Bridge agent id |
| crew | str | Crew membership (CR-0003) |
| prompt | str | Operator-editable instructions folded into the system prompt |

#### CoordinatorData (TypedDict)

```python
class CoordinatorData(TypedDict):
    connected: bool
    bridge_status: str                    # ok, warning, error (tri-state mapped, US0028)
    bridge_version: str
    bridge_uptime: int
    agent_count_healthy: int
    agent_count_total: int
    agents: list[AgentInfo]
    last_poll: str                        # ISO timestamp
    # /v1/health tri-state surface (US0028/AC4); only set on the success path, so
    # the hard-error CoordinatorData omits them -- typed NotRequired, read via .get().
    tool_surface: NotRequired[str]
    read_only_safe: NotRequired[bool]
    # CR-0009 observability, refreshed on the discovery cadence; read via .get().
    usage: NotRequired[dict[str, dict[str, Any]]]   # AgentUsageSummary keyed by agent_id
    doctor: NotRequired[dict[str, Any]]             # fleet-doctor verdict payload
```

`usage` and `doctor` are best-effort (an older bridge without the endpoints, or a
transient per-agent failure, keeps the last-known values) and are carried forward
through connectivity outages so sensors and the repair issue do not blank (BG0007).
The coordinator emits shallow copies so consumers cannot mutate its working maps
(BG0008).

**Webhook push validation (CR-0014):** the HA webhook is unauthenticated by design
(the id is the credential), so `async_push_webhook_data` validates pushed data
before it reaches sensor state: a bridge-status push must be a string in the known
health vocabulary (whitelist); a per-agent push must carry a typed `agentId: str` +
`healthy: bool` exactly. Malformed pushes are ignored; a push for an unknown agent
triggers a fresh poll instead of a blind write.

#### AgentInfo (TypedDict — v4.x discovery surface, US0028)

```python
class AgentInfo(TypedDict):
    id: str
    name: str
    description: str
    healthy: bool             # health.state in (ready, healthy) AND circuit == closed
    adapter: str
    capabilities: dict[str, Any]
    tags: list[str]
    # CR-0097 health block
    health_state: str
    circuit: str
    inflight: int
    last_seen_at: str
    stale_after: int
    # CR-0245 metrics
    latency_ms: float
    requests: int
    errors: int
    # CR-0256/0247/0259 taxonomy (voice-capability gating + pickers)
    agent_class: str
    identity_substrate: str
    capability_envelope: dict[str, Any]
    is_orchestrator: bool
    framework: str
    effective_model: str
    model_provider: str
    deprecated: bool
    crew: str                 # from ?include=crew (CR-0003)
```

### Storage Strategy

| Data Type | Storage | Rationale |
|-----------|---------|-----------|
| Config | HA config entry (encrypted `.storage/`) | HA standard, secrets protected |
| Session channel epochs | In-memory per conversation entity (US0032) | The bridge persists per-channel context (24h TTL); HA only rotates the key. The v0.1 HA Store was retired |
| Coordinator state | In-memory | Rebuilt from bridge on each poll |
| Conversation history | HA `ChatLog` (per conversation) + bridge channels (cross-turn agent context) | Bridge owns cross-session persistence |
| Entity exposure | Computed per request | Must reflect current state |

---

## 7. Integration Patterns

### External Services

| Service | Purpose | Protocol | Auth |
|---------|---------|----------|------|
| Agent Bridge | All agent communication | REST (aiohttp) | Bearer token |
| HA Entity Registry | Entity state for exposure | Internal Python API | N/A |
| HA Device Registry | Device-to-area mapping | Internal Python API | N/A |
| HA Area Registry | Area names for room awareness | Internal Python API | N/A |
| HA Conversation API | Register as conversation agent | Internal Python API | N/A |

### Event Architecture

Internal HA events (fired via `hass.bus.async_fire`):

| Event | Trigger | Data Fields |
|-------|---------|-------------|
| `agent_bridge_message_received` | Agent responds to conversation | agent_id, model, content_preview, awaiting_confirmation, severity |
| `agent_bridge_actuation_audit` | Once per reactive conversation turn (US0027/AC3 — the HA-side hook US0031 wires to the bridge audit log) | agent_id, conversation_id, area, is_voice, source_type, account_verified, risky_domains_exposed, reply_preview, awaiting_confirmation, severity |
| `agent_bridge_agent_discovered` | New agent appears in discovery | agent_id, name, capabilities |
| `agent_bridge_agent_removed` | Agent disappears from discovery | agent_id, name |
| `agent_bridge_bridge_upgraded` | Bridge `bridge:upgraded` webhook event (drift signal, US0024/US0029) | webhook event data |

### Webhook Lifecycle (CR-0014)

Bridge events reach HA through a hardened webhook subscription (`webhook.py`):

1. **Persistent id:** the HA webhook id is generated once and stored in
   `entry.data[CONF_WEBHOOK_ID]`; restarts reuse it, so the bridge subscription
   does not churn. The id is the credential (HA webhooks are unauthenticated by
   design) and is logged at DEBUG only.
2. **Stale-subscription cleanup:** before registering, a bridge subscription
   leaked by a previous unclean shutdown (persisted
   `entry.data[CONF_WEBHOOK_SUBSCRIPTION_ID]`) is unregistered best-effort, so at
   most one live subscription exists.
3. **Hardened registration:** the HA webhook is registered `local_only=True` and
   `allowed_methods=["POST"]` (the bridge posts from the LAN). A stale handler
   left by a mid-setup failure is replaced rather than failing setup.
4. **Bridge subscription:** `POST /v1/webhooks` subscribes the HA callback URL to
   the full event catalogue (`agent:registered/unregistered/updated`,
   `agent:health-changed`, `message:sent/error`, `bridge:upgraded`). Failure is
   non-fatal — the integration falls back to polling.
5. **Dispatch:** `agent:health-changed` → validated coordinator push;
   roster events → immediate coordinator refresh; `bridge:upgraded` →
   `agent_bridge_bridge_upgraded` (re-runs the drift check); `message:error` →
   warning log. Non-object/invalid JSON payloads get a clean 400 (BG0014).
6. **Unload:** the webhook is unregistered from both the bridge and HA;
   registration runs before the options listener is added so persisting the ids
   cannot trigger a reload loop.

---

## 8. Infrastructure

### Deployment Topology
The integration runs inside the Home Assistant process. No separate deployment.

```
Home Assistant (10.0.0.209)
  └── custom_components/agent_bridge/
        └── Talks to Agent Bridge (10.0.0.206:18780) via HTTP
```

### Environment Strategy

| Environment | Purpose | Characteristics |
|-------------|---------|-----------------|
| Development | Local HA dev instance | Mock bridge responses, pytest |
| Production | Live HA on homeautoserver | Real bridge, real agents |

### manifest.json

```json
{
    "domain": "agent_bridge",
    "name": "Agent Bridge",
    "codeowners": ["@DarrenBenson"],
    "config_flow": true,
    "dependencies": ["conversation"],
    "documentation": "https://github.com/Engram-Labs-UK/agent-bridge-ha",
    "iot_class": "local_polling",
    "issue_tracker": "https://github.com/Engram-Labs-UK/agent-bridge-ha/issues",
    "requirements": [],
    "version": "0.11.0"
}
```

**Key fields:**
- `config_flow: true` -- enables UI-based setup (Settings > Add Integration)
- `iot_class: local_polling` -- bridge is local network, integration polls for data
- `requirements: []` -- no pip dependencies beyond HA-bundled packages
- `dependencies: ["conversation"]` -- the conversation component must be loaded before the per-agent entities

### HACS Distribution

```json
{
    "name": "Agent Bridge",
    "render_readme": true,
    "homeassistant": "2025.7.0"
}
```

Repository structure for HACS:

```
agent-bridge-ha/
├── custom_components/
│   └── agent_bridge/
│       ├── __init__.py
│       ├── ai_task.py
│       ├── binary_sensor.py
│       ├── client.py
│       ├── config_flow.py
│       ├── const.py
│       ├── conversation.py
│       ├── coordinator.py
│       ├── diagnostics.py
│       ├── drift.py
│       ├── event.py
│       ├── exposure.py
│       ├── helpers.py
│       ├── sensor.py
│       ├── services.py
│       ├── webhook.py
│       ├── manifest.json
│       ├── services.yaml
│       ├── strings.json
│       ├── brand/
│       └── translations/
│           └── en.json
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   │   └── bridge_openapi_contract.json
│   ├── test_agent_selection.py
│   ├── test_ai_task.py
│   ├── test_binary_sensor.py
│   ├── test_broadcast.py
│   ├── test_client.py
│   ├── test_config_flow.py
│   ├── test_conversation.py
│   ├── test_conversation_integration.py
│   ├── test_coordinator.py
│   ├── test_diagnostics.py
│   ├── test_drift_surface.py
│   ├── test_event.py
│   ├── test_exposure.py
│   ├── test_helpers.py
│   ├── test_openapi_contract.py
│   ├── test_sensor.py
│   ├── test_services.py
│   ├── test_streaming.py
│   └── test_webhook.py
├── hacs.json
├── CLAUDE.md
├── AGENTS.md
├── README.md
├── sdlc-studio/
│   ├── prd.md
│   ├── trd.md
│   └── tsd.md
└── .github/
    └── workflows/
        └── validate.yml
```

---

## 8a. Module Specifications

### const.py

```python
DOMAIN = "agent_bridge"
PLATFORMS = ["conversation", "sensor", "binary_sensor", "event", "ai_task"]

# Config subentries (US0025) + per-agent instructions (CR-0003)
SUBENTRY_TYPE_CONVERSATION = "conversation"
CONF_AGENT_ID = "agent_id"
CONF_CREW = "crew"
CONF_PROMPT = "prompt"
DEFAULT_PROMPT = "This request comes from Home Assistant Assist. ..."  # origin/role layer

# Config entry keys
CONF_BRIDGE_URL = "bridge_url"
CONF_BRIDGE_TOKEN = "bridge_token"
CONF_DEFAULT_AGENT = "default_agent"
CONF_VOICE_AGENT = "voice_agent"
CONF_CONTEXT_MAX_CHARS = "context_max_chars"
CONF_THINKING_TIMEOUT = "thinking_timeout"
CONF_SSL_VERIFY = "ssl_verify"
CONF_DOCTOR_ALERTS = "doctor_alerts"                    # CR-0012 opt-in repair
CONF_WEBHOOK_SUBSCRIPTION_ID = "webhook_subscription_id" # CR-0014 stale-sub cleanup
CONF_SESSION_IDLE_WINDOW = "session_idle_window"        # US0032
CONF_ENABLE_STREAMING = "enable_streaming"              # US0033

# Defaults
DEFAULT_CALLER_ID = "homeassistant"        # last-resort x-bridge-mcp-caller
DEFAULT_BRIDGE_URL = "http://localhost:18780"
DEFAULT_CONTEXT_MAX_CHARS = 13000
DEFAULT_THINKING_TIMEOUT = 120
DEFAULT_SESSION_IDLE_WINDOW = 300
SESSION_IDLE_PRESETS = (0, 300, 1800, 7200, 28800, 86400)  # CR-0013 dropdown
DEFAULT_ENABLE_STREAMING = False
DEFAULT_POLL_INTERVAL = 30                 # seconds
DEFAULT_DISCOVERY_INTERVAL = 300           # seconds
DEFAULT_STREAMING_TIMEOUT = 300            # seconds
MAX_ENTITIES = 250
MAX_TEXT_DEPTH = 8                         # recursive response text extraction

# Drift baselines (US0029) -- keep the HA pin in sync with CI (Critical Rule 9)
TESTED_BRIDGE_VERSION = "4.141.0"
TESTED_HA_VERSION = "2026.2.3"

# Event types
EVENT_MESSAGE_RECEIVED = f"{DOMAIN}_message_received"
EVENT_AGENT_DISCOVERED = f"{DOMAIN}_agent_discovered"
EVENT_AGENT_REMOVED = f"{DOMAIN}_agent_removed"
EVENT_BRIDGE_UPGRADED = f"{DOMAIN}_bridge_upgraded"
EVENT_ACTUATION_AUDIT = f"{DOMAIN}_actuation_audit"     # US0027/AC3

# Safety deny/confirm domains (US0027) -- folded into the grounding caution
DENY_CONFIRM_DOMAINS = frozenset({"lock", "alarm_control_panel", "climate",
                                  "water_heater", "cover"})

# Bridge webhook event catalogue (US0024)
BRIDGE_WEBHOOK_EVENTS = ("agent:registered", "agent:unregistered", "agent:updated",
                         "agent:health-changed", "message:sent", "message:error",
                         "bridge:upgraded")

# Response text extraction priority keys
TEXT_PRIORITY_KEYS = ("text", "content", "message", "output_text")

# Continuation detection defaults (fixed constants)
DEFAULT_CONTINUATION_PHRASES = (...)
DEFAULT_CONTINUATION_EXCLUSIONS = (...)
```

### services.yaml

Defines the HA service schemas rendered in the developer tools UI:

| Service | Fields | Required |
|---------|--------|----------|
| `send_message` | message (str), agent_id (str — defaults to the configured default agent), session_id (str) | message |
| `invoke_tool` | agent_id (str), tool_name (str), args (object) | agent_id, tool_name |
| `broadcast` | message (str), tags (list[str] — defaults to `['operator']`) | message |
| `ask_with_image` | message (str), camera_entity_id (entity id), agent_id (str), session_id (str) | message, camera_entity_id |
| `announce` | message (str), target (assist_satellite entity id), priority (low/normal/critical) | message, target |
| `memory_record` | content (str), agent_id (str), tags (list[str]) | content |
| `memory_recall` | query (str), agent_id (str) | — |

### strings.json / translations/en.json

User-facing strings for the config flow and options flow:

| Key Path | Purpose |
|----------|---------|
| `config.step.user.title` | "Agent Bridge" |
| `config.step.user.data.bridge_url` | "Bridge URL" |
| `config.step.user.data.bridge_token` | "API Token" |
| `config.step.agents.title` | "Select Agents" |
| `config.step.agents.data.default_agent` | "Default Chat Agent" |
| `config.step.agents.data.voice_agent` | "Voice Agent" |
| `config.error.cannot_connect` | "Cannot connect to bridge" |
| `config.error.invalid_auth` | "Invalid API token" |
| `options.step.init.data.*` | Options flow field labels |

---

## 9. Security Considerations

### Threat Model

| Threat | Likelihood | Impact | Mitigation |
|--------|-----------|--------|------------|
| Bridge token leaked in logs | Medium | High | Never log token value; redacted in the diagnostics download (with any orphaned `caller_id`) |
| Man-in-middle on bridge connection | Low | Medium | SSL/TLS support; verification on by default (first-run toggle, CR-0016) |
| Forged webhook push poisons sensor state | Medium | Medium | Webhook is local-only + POST-only; pushed status whitelisted against the health vocabulary; per-agent pushes require typed `agentId`/`healthy` (CR-0014) |
| Webhook id leaked | Low | Medium | The id is the credential: generated once, persisted in the encrypted entry, logged at DEBUG only (CR-0014) |
| Prompt injection via HA state into the agent | Low | Medium | Source metadata rendered in a labelled system block separate from the utterance; automation-sourced turns flagged for stricter gating |
| Agent actuates a safety-relevant device unprompted | Low | High | Deny/confirm caution + `[confirm:LEVEL]` contract (US0036); exposure is fail-closed; the agent's own `/api/mcp` mount enforces HA's exposure/auth on the actuation side |
| Excessive entity exposure | Low | Low | 250 entity cap; respects HA expose settings |

### Security Controls

| Control | Implementation |
|---------|----------------|
| Authentication | Bearer token in Authorization header; `x-bridge-mcp-caller` caller identity (BG0004) |
| Token storage | HA encrypted config entry (not plaintext) |
| SSL/TLS | Supported with configurable verification (default on) |
| Entity access | HA's native expose settings control what agents see in the grounding hint (fail-closed) |
| Actuation boundary | No HA-side tool executor exists (ADR-006); actuation authority lives with the agent's `/api/mcp` mount, audited via `agent_bridge_actuation_audit` per reactive turn |
| Webhook hardening | Local-only, POST-only registration; validated pushes; persistent id; stale-subscription cleanup (CR-0014) |
| Diagnostics redaction | `bridge_token` and legacy `caller_id` redacted from the diagnostics download |

---

## 10. Performance Requirements

### Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| Entity context build time | < 500ms for 250 entities | Timed in conversation agent |
| Coordinator poll overhead | < 100ms per cycle | Timed in coordinator update |
| Conversation round-trip | < bridge response time + 200ms | Timed end-to-end in conversation agent |
| Config flow discovery | < 5s | Timed in config flow step 1 |

---

## 11. Architecture Decision Records

### ADR-001: Thin Adapter vs Full Integration

**Status:** Accepted

**Context:** The OpenClaw HA integration duplicates some bridge-like logic (session management, model selection, retry handling). Should this integration follow the same pattern or be thinner?

**Decision:** Thin adapter. The Agent Bridge already handles routing, resilience, session management, and model selection. Duplicating this in the HA component creates maintenance burden and divergence risk.

**Consequences:**
- Positive: Less code, fewer bugs, single source of truth for agent management
- Positive: Bridge improvements automatically benefit HA integration
- Negative: HA integration has less standalone capability if bridge is down (mitigated by graceful degradation)

### ADR-002: Polling vs Webhooks for Health

**Status:** Accepted

**Context:** The bridge supports webhook subscriptions for real-time events. Should the integration use webhooks or polling?

**Decision:** Polling first (Phase 1), with webhook support as Phase 2. Polling at 30s intervals is adequate for homelab scale and avoids the complexity of HA needing a reachable callback URL.

**Consequences:**
- Positive: Simpler implementation, no networking requirements
- Negative: Up to 30s delay in health status updates (acceptable for homelab)

*Update (CR-0014, 2026-07-04): Phase 2 shipped — polling remains the backbone, with a hardened webhook subscription layered on top for real-time pushes (see §7 Webhook Lifecycle). Webhook failure degrades gracefully to polling.*

### ADR-003: Per-Agent Entities as Opt-In

**Status:** Accepted

**Context:** Should every bridge agent automatically get a conversation entity and health sensor in HA, or should this be opt-in?

**Decision:** Opt-in via `enable_per_agent_entities` option. Default off. The primary conversation agent (routing through bridge default) covers the common case. Per-agent entities add value for multi-satellite setups but create entity clutter for simpler configurations.

**Consequences:**
- Positive: Clean default experience with one conversation agent
- Positive: Power users can enable per-agent control
- Negative: Two-step setup for multi-agent users (enable option, then configure pipelines)

*Update (US0025/CR-0006, 2026-07-04): the option flag is gone — the opt-in intent survives as **config subentries**: the operator adds each agent explicitly (crew → agent → instructions), which is HA's modern pattern for per-agent entities.*

### ADR-004: Entity Exposure from OpenClaw Fork

**Status:** Accepted

**Context:** The OpenClaw HA fork has a battle-tested entity exposure system that formats HA entities with areas, attributes, and caps. Should we rewrite or adapt?

**Decision:** Adapt the OpenClaw fork's `exposure.py` patterns. The formatting logic, attribute selection, area injection, and 250-entity cap are well-proven.

**Consequences:**
- Positive: Proven approach, known to work with voice assistants
- Positive: Faster implementation (adapt, not rewrite)
- Negative: Need to refactor from OpenClaw-specific patterns to generic bridge patterns

### ADR-005: Tool Execution Architecture

**Status:** SUPERSEDED by **ADR-006** (EP0007 / CR-0006, 2026-06-09) — the HA-side
tool-execution loop described here was removed. The agent actuates Home Assistant
through its **own `/api/mcp` mount** (Option A, US0027/US0031); this integration runs
no tool loop and parses no `tool_calls`. Retained for the historical record.

**Context:** When an agent returns `tool_calls` in a chat completion response, the integration must execute HA services and return results. This involves several non-obvious design choices: how many iterations to allow, how to handle batch calls, what to do when the response contains both text content and tool_calls, and how to report failures.

**Decisions:**

**1. Loop cap: 10 iterations per conversation turn.**
A confused or misconfigured agent could loop indefinitely (return tool_calls → receive results → return more tool_calls). The 10-iteration cap is a safety net separate from `thinking_timeout`. Typical voice commands resolve in 1-2 rounds. Complex multi-step commands ("set the house to night mode" touching lights, thermostat, locks, media, blinds) need at most 5-6 rounds. 10 provides 2x headroom. Beyond 10, the agent is not making progress. The user receives a clear error: "Agent could not complete the request."

Alternative considered: No cap, rely solely on `thinking_timeout` (120s). Rejected because a fast agent could execute 100+ iterations in 120s, wasting bridge resources and HA service calls.

**2. Content + tool_calls: Execute tools first, preserve content in message history.**
The OpenAI format allows both `content` ("Sure, I'll turn on the lights") and `tool_calls` in the same message. The integration always executes the tool_calls and sends results back to the agent for a final response -- even when content is present. The prior content is preserved in the message history so the agent has full context.

Alternative considered: Return the content immediately to the user and execute tools in background. Rejected because ConversationResult cannot be amended after return -- if the tool fails, the user heard a lie ("I've turned on the lights" when they didn't turn on).

**3. Batch execution: Parallel via `asyncio.gather(return_exceptions=True)`.**
When `execute_services` (plural) contains multiple service calls, all execute in parallel. Each call's result is reported individually: `[{"entity_id": "light.kitchen", "success": true}, {"entity_id": "light.study", "success": false, "error": "timeout"}]`. The agent receives the full picture and can report partial success.

Alternative considered: Sequential execution. Rejected because latency scales linearly (5 entities × 10s timeout = 50s worst case vs 10s parallel). If ordering matters, the agent should use separate sequential tool_calls across multiple messages, not a single batch.

**4. Error format: JSON results to agent, not Python exceptions.**
Tool failures (entity not found, service timeout, invalid domain) are returned as JSON tool results, not raised as exceptions. This lets the agent report partial success: "I turned off the ceiling light and desk lamp, but the study lamp wasn't found." Raising exceptions would abort the entire conversation on any single failure.

**Consequences:**
- Positive: Robust handling of the full OpenAI tool calling protocol
- Positive: Graceful partial success for multi-entity commands
- Positive: Safety against infinite tool call loops
- Positive: Accurate user responses grounded in actual tool outcomes
- Negative: Extra round-trip when content + tool_calls arrive together (acceptable -- tool execution is already the slow path)

### ADR-006: Agent-Owned Actuation via `/api/mcp` (Option A)

**Status:** Accepted (EP0007, 2026-06-09; formalised by CR-0011, 2026-07-04). Supersedes ADR-005.

**Context:** The CR-0002 audit found the ADR-005 tool-execution loop structurally
inert: neither modern HA's conversation pipeline nor the v4.36+ bridge carries a
`tool_calls` contract on the reactive path, so the loop could never fire — the
integration described actuation it could not perform. The US0021 spike evaluated
two designs: **(a)** round-tripping HA's LLM-API `llm.Tool` surface through the
bridge (requires a bridge tool-call contract that does not exist), and **(b)** the
refined **Option A** — the agent already runs its own harness with an HA MCP mount
(the DBee pattern), so it can read and control Home Assistant directly via
`/api/mcp` (HA's MCP Server integration). A live-fleet consult confirmed the
agents prefer owning actuation.

**Decision:** Actuation is **agent-owned**. This integration is the Assist
front-end only: it forwards the utterance + a fail-closed entity grounding hint +
the structured `caller_context` envelope as free text, and returns the agent's
reply. It runs **no HA-side tool loop**, parses no `tool_calls`, and never calls
`hass.services.async_call()` on the agent's behalf. The agent reads live HA state
and actuates through its own `/api/mcp` mount, where HA's exposure and
authentication apply (US0027/US0031). (The `agent_bridge.invoke_tool` service is a
separate, operator-facing direct call to `/v1/tools/invoke` — not part of the
conversation loop.)

**Safety and audit surfaces:**
- **Audit:** HA fires `agent_bridge_actuation_audit` (`EVENT_ACTUATION_AUDIT`)
  once per reactive turn — agent, conversation id, area, source type, account
  verification, exposed risky domains, reply preview, confirmation state. This is
  the documented HA-side hook that US0031 wires to the bridge audit log; the
  agent's mount emits the authoritative per-actuation event.
- **Deny/confirm:** when exposed entities include safety-relevant domains
  (`lock`, `alarm_control_panel`, `climate`, `water_heater`, `cover`), the
  grounding prompt folds in a caution: ask a yes/no question first, prefixed
  `[confirm:high]` (or `normal`/`low`). HA strips the marker, surfaces the
  severity on its events, and keeps the conversation open (US0036). On the
  streaming path the marker is stripped from the **head of the delta stream**,
  before any content reaches TTS or the stored `ChatLog` turn (BG0012).
- **Grounding, not authority:** the exposure context is a hint; the agent reads
  live state back after acting to verify the result.

**Consequences:**
- Positive: The reactive path actually actuates — with no bridge protocol change
- Positive: One actuation authority (the agent's mount) with HA-native
  exposure/auth enforcement; no duplicated tool executor to keep in sync
- Positive: Massive code cull (`tool_executor.py`, the loop cap, batch rules, and
  `enable_tool_calls` all removed — CR-0006)
- Negative: HA cannot observe individual service calls made by the agent; the
  per-turn audit event + the agent-side audit log are the compensating record
- Negative: Depends on each agent's harness mounting HA MCP correctly
  (`toolSurface`/`readOnlySafe` from `/v1/health` diagnose that gap)

---

## 12. Open Technical Questions

- [x] **Q:** Should the integration create a bridge channel per HA conversation ID for multi-turn voice?
  **Context:** Bridge channels persist conversation history. Creating one per HA conversation ID enables multi-turn voice dialogue. But channel cleanup becomes an issue if HA creates many short-lived conversations.
  **Decision:** One session per agent (not per conversation_id), persisted to HA Store. Session ID format: `agent:{agent_id}:assist_{random_hex}`. Sent as `channel` field in chat requests. See PRD Session Persistence feature (EP0002). *(Superseded by US0032: the HA Store was retired — the bridge persists per-channel context (24h TTL), and HA sends idle-windowed channel keys `ha:{agent_id}:{scope}:{epoch}` that rotate after an idle gap. See PRD Session Continuity.)*

- [x] **Q:** How should entity exposure handle template entities and groups?
  **Context:** Template sensors and groups can have complex state. Should they be exposed as-is, or filtered?
  **Decision:** Expose as-is with no type-based filtering. Rationale: (1) Consistent with ADR-001 -- the integration is a thin adapter that respects HA's expose settings, not a second filtering layer. (2) Template entities often contain the most valuable computed state for agents (e.g. `binary_sensor.house_occupied`, `sensor.total_power_draw`). (3) Groups provide relationship context that helps agents handle commands like "turn off everything in the kitchen". (4) The 250-entity cap already prevents prompt bloat. (5) Other HA conversation agents (Google Home, Alexa) follow the same pattern. If a user doesn't want an entity exposed, they un-expose it in HA -- the integration doesn't second-guess.

---

## 13. Implementation Constraints

### Must Have
- Compatible with Home Assistant Core 2025.7.0+ (HACS floor); built + CI-tested against the pinned HA **2026.2.3** on Python 3.13 (`const.TESTED_HA_VERSION` and CI `HA_VERSION` move together — US0029 / Critical Rule 9)
- No additional pip dependencies (only HA-bundled packages)
- HACS-installable repository structure
- Works with Agent Bridge v4.x REST API; tested baseline **v4.141.0** (`const.TESTED_BRIDGE_VERSION`); the agent-context drift check raises a repair issue when the live bridge moves past the baseline
- British English in all user-facing strings

### Won't Have (This Version)
- Direct agent communication (always goes through bridge)
- Local agent execution (bridge handles all agent backends)
- Custom Lovelace card (stripped from OpenClaw -- use standard HA cards)
- WebSocket API for chat history (stripped from OpenClaw)
- OpenClaw addon auto-discovery (not relevant)
- Model selection entity (bridge handles model selection per agent)

---

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2026-04-05 | 0.1.0 | Initial TRD -- greenfield architecture |
| 2026-04-05 | 0.1.1 | RV0001 review: added Session Manager, Continuation Detector, Voice Debug Logger to component table; added SSE Streaming architecture; specified const.py, services.yaml, strings.json contents; noted shallow/deep health response shape difference |
| 2026-04-05 | 0.1.2 | TRD review: fixed /v1/discovery auth, added tool executor rules, manifest.json spec, missing test files, resolved open questions, fixed hacs.json, documented status→bool mapping |
| 2026-04-05 | 0.1.3 | Resolved all open questions (Q1: session-per-agent, Q2: expose all entity types as-is). Added ADR-005: Tool Execution Architecture (loop cap, content+tool_calls, parallel batch, JSON error format) |
| 2026-06-09 | 0.10.0 | RV0006 release-gate review: added a currency note (top) with the post-CR-0006..0010 deltas; marked ADR-005 + §4 tool-execution SUPERSEDED (agent-owned `/api/mcp` actuation). Full interface/endpoint/module reconcile tracked in CR-0011. |
| 2026-07-04 | 0.11.1 | CR-0011 full reconcile to shipped code: §5 rewritten to the client-method/endpoint reality (agent_usage, doctor, memory_record/recall, agent_health, agent_context; CR-0015 URL-encoded path parameters; `caller_context` chat envelope; v4.36 SSE shape; crew-aware discovery + agent_label naming); tool-call sections replaced by the Option A actuation flow; §6 CoordinatorData/AgentInfo/options updated (NotRequired usage/doctor/tool_surface/read_only_safe; CR-0014 webhook push validation); §7 event table + webhook lifecycle (persistent id, stale-subscription cleanup, local-only/POST-only); §3.1/§8/§8a module tables + repo structure match the code (ai_task/diagnostics/drift/webhook added, tool_executor removed); new **ADR-006** (agent-owned `/api/mcp` actuation) supersedes ADR-005; §9 security + §13 constraints re-baselined (bridge v4.141.0 / HA 2026.2.3). |
