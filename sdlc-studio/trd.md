# Technical Requirements Document

**Project:** Agent Bridge HA
**Version:** 0.1.0
**Status:** Draft
**Last Updated:** 2026-06-01
**Last Review:** 2026-06-01 — reconcile + prd/trd/tsd review vs bridge v4.36 + current HA APIs (CR-0002 redesign basis)
**PRD Reference:** [PRD](prd.md)

> ⚠️ **Review banner (2026-06-01):** This TRD targets **Agent Bridge v3.1.0+** and HA's legacy conversation API; both have drifted. A verified audit (CR-0002) found: **(a)** the reactive `tool_calls` actuation loop is inert — neither HA nor the **v4.36** bridge carries a `tool_calls` contract; **(b)** the component is on HA's legacy `AbstractConversationAgent`/`async_set_agent`, not `ConversationEntity`/`ChatLog`/LLM-API; **(c)** request/response shapes drifted: `/v1/tools/invoke` (`agent`/`tool`, not `agent_id`/`tool_name`), `/v1/broadcast` (`messages[]`+`tags`, responses-object), SSE (`event:message {text}` + `event:done`, **not** `choices[].delta`/`[DONE]`), webhook health (`{agentId,healthy}`). The redesign + the full TRD rewrite to the v4.36/ConversationEntity model are **[CR-0002](change-requests/cr0002.md)** / **[EP0007](epics/EP0007-bridge-v436-modern-ha-realignment.md)** (rewrite tracked by **US0030**). Sections below are the **v0.1 record**; the two clear factual errors are corrected inline this pass.

---

## 1. Executive Summary

### Purpose
Define the technical architecture for Agent Bridge HA -- a Home Assistant custom component that exposes Agent Bridge agents as native HA conversation agents with entity exposure, room awareness, health monitoring, and automation events.

### Scope
- Async HTTP client for the Agent Bridge REST API
- HA config flow with bridge discovery and agent selection
- DataUpdateCoordinator for bridge health polling
- Conversation agent registration (single default + optional per-agent)
- Entity exposure system (HA entity state formatted for AI consumption)
- Room/area awareness for voice requests
- HA service execution from agent tool_call responses (the mechanism by which agents control the home)
- Sensor, binary_sensor, and event entity platforms
- HA services for message sending and tool invocation
- HACS distribution

### Key Decisions
- Thin adapter: all routing, resilience, and agent management delegated to the bridge
- No new pip dependencies beyond what HA bundles (aiohttp, voluptuous)
- Per-agent entities gated behind an option flag (opt-in, not default)
- Entity exposure cherry-picked from OpenClaw fork patterns (proven in production)
- Conversation history managed by bridge channels, not by the integration
- Polling-first for health (webhooks deferred to Phase 2)

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
| Bridge Client | HTTP communication with Agent Bridge REST API | aiohttp (HA shared session) |
| Config Flow | UI-driven setup and options | HA ConfigFlow, voluptuous |
| Data Coordinator | Periodic bridge health/discovery polling | HA DataUpdateCoordinator |
| Conversation Agent | HA Assist integration, prompt building, tool call loop | HA AbstractConversationAgent |
| Tool Executor | Execute HA services from agent tool_call responses | HA service registry |
| Entity Exposure | Format HA entity state for AI context | HA entity/device/area registries |
| Sensor Platform | Bridge health and agent count sensors | HA SensorEntity |
| Binary Sensor Platform | Connectivity and per-agent health sensors | HA BinarySensorEntity |
| Event Platform | Message and tool invocation events | HA EventEntity |
| Service Handler | send_message, invoke_tool, broadcast services | HA service registry |
| Session Manager | Agent-scoped session persistence via HA Store (lives in `__init__.py`, not a separate file) | HA Store (`.storage/`) |
| Continuation Detector | Analyse agent responses for follow-up question patterns | Internal (in conversation.py) |
| Voice Debug Logger | Detailed logging of voice routing decisions (agent, session, area) | Python logging |
| Helpers | Response text extraction, text normalisation | Internal |

---

## 4. Technology Stack

### Core Technologies

| Category | Technology | Version | Rationale |
|----------|-----------|---------|-----------|
| Language | Python | 3.12+ | HA requirement |
| Framework | Home Assistant Core | 2025.1.0+ | Target platform |
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

### Bridge API Endpoints Consumed

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| `GET` | `/health` | Connectivity check and bridge status | No |
| `GET` | `/health?depth=shallow` | Bridge status + agent counts (polling) | No |
| `GET` | `/v1/health` | Per-agent readiness (tri-state rollup, `toolSurface`, `readOnlySafe`) | Yes |
| `GET` | `/v1/discovery` | Agent list with capabilities and health | Yes |
| `POST` | `/v1/chat/completions` | Send message to agent | Yes |
| `POST` | `/v1/tools/invoke` | Invoke agent tool | Yes |
| `POST` | `/v1/broadcast` | Send to multiple agents | Yes |
| `POST` | `/v1/webhooks` | Register event subscription (Phase 2) | Yes |
| `DELETE` | `/v1/webhooks/:id` | Remove event subscription (Phase 2) | Yes |

### Chat Request Format (sent to bridge)

```python
{
    "messages": [
        {"role": "system", "content": "<room_context>\n<entity_context>\n<extra_system_prompt>"},
        {"role": "user", "content": "<user_message>"}
    ],
    "agent": "<agent_id>",              # From config: default_agent or voice_agent
    "channel": "<agent_scoped_session>", # Persistent session for multi-turn context
    "metadata": {                        # Optional voice context (omitted for text input)
        "source": "voice",               # "voice" or "text" -- agents use this to format responses
        "device_id": "<ha_device_id>",   # HA device registry ID of the input device
        "satellite_id": "<ha_sat_id>",   # Satellite ID (HA 2025+, may differ from device_id)
        "area": "<area_name>",           # Resolved human-readable area name (e.g. "Kitchen")
        "language": "<language_code>"    # e.g. "en" -- from ConversationInput.language
    }
}
```

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

### Chat Response with Tool Calls (received from bridge)

When the agent decides to control HA devices, it returns tool_calls instead of (or alongside) content:

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
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_abc123",
                        "type": "function",
                        "function": {
                            "name": "execute_service",
                            "arguments": "{\"domain\": \"light\", \"service\": \"turn_on\", \"entity_id\": \"light.kitchen\"}"
                        }
                    }
                ]
            },
            "finish_reason": "tool_calls"
        }
    ]
}
```

### Tool Call Execution Flow

```
1. User: "Turn on the kitchen lights"
         │
2. Integration builds system prompt (entity context + room)
         │
3. POST /v1/chat/completions → Agent Bridge → Agent
         │
4. Agent responds with tool_calls: execute_service(light.turn_on, light.kitchen)
         │
5. Integration validates entity_id against exposure list
         │
6. Integration calls: hass.services.async_call("light", "turn_on", target={"entity_id": "light.kitchen"})
         │
7. Integration sends tool result back to bridge:
   POST /v1/chat/completions with tool_call result messages
         │
8. Agent formulates final response: "Done, I've turned on the kitchen lights."
         │
9. Integration returns ConversationResult with speech text
```

The tool call loop may iterate multiple times if the agent needs to call several services before formulating a final response.

**Tool Executor Rules:**
- **Loop cap:** Maximum 10 iterations per conversation turn. If the agent keeps returning tool_calls after 10 rounds, return an error message to the user ("Agent could not complete the request").
- **Content + tool_calls:** When the response contains both `content` and `tool_calls`, execute the tool_calls first, then include the content as context in the next request. The final response to the user comes from the last agent reply that has content and no tool_calls.
- **Batch execution:** When `execute_services` (plural) is the tool name, the `arguments` contain a list of service calls. Execute all in parallel via `asyncio.gather()`, collect results, and send them back as a single tool result.
- **Error result format:** Failed tool calls return a descriptive JSON error (not a Python exception):
  ```python
  {"success": false, "error": "Entity light.kitchen not found in exposed entities"}
  {"success": false, "error": "Service call timed out after 10s"}
  {"success": false, "error": "Domain 'invalid' not found"}
  ```
- **Success result format:** Successful tool calls return confirmation:
  ```python
  {"success": true, "entity_id": "light.kitchen", "service": "light.turn_on"}
  ```

### Tool Call Message Format (sent back to bridge)

```python
{
    "messages": [
        {"role": "system", "content": "<system_prompt>"},
        {"role": "user", "content": "Turn on the kitchen lights"},
        {"role": "assistant", "content": None, "tool_calls": [{"id": "call_abc123", ...}]},
        {"role": "tool", "tool_call_id": "call_abc123", "content": "{\"success\": true}"}
    ],
    "agent": "cora",
    "channel": "<session_id>"
}
```

### SSE Streaming (Phase 2)

The bridge client supports optional Server-Sent Events streaming for chat completions:

```python
# Stream request (adds stream=True to chat request)
{
    "messages": [...],
    "agent": "cora",
    "channel": "<session_id>",
    "stream": True
}

# SSE chunks (text/event-stream)
data: {"id": "chatcmpl-xxx", "choices": [{"delta": {"content": "I've"}}]}
data: {"id": "chatcmpl-xxx", "choices": [{"delta": {"content": " turned"}}]}
data: [DONE]
```

**Client behaviour:**
- `chat()` accepts optional `stream: bool` parameter (default: `False`)
- When streaming, returns an async iterator of content deltas
- Conversation agent assembles deltas into complete `ConversationResult`
- On SSE parse error or timeout, falls back to non-streaming retry
- Streaming timeout configurable (default 300 seconds, separate from `thinking_timeout`)

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

### Discovery Response Format

```python
{
    "agents": [
        {
            "id": "cora",
            "name": "Cora",
            "description": "Primary AI assistant",
            "status": "healthy",
            "adapter": "http-openai",
            "capabilities": {"chat": true, "tools": ["web_search", "email"], "streaming": true},
            "tags": ["primary", "nlp"]
        }
    ]
}
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
| `AUTH_REQUIRED` | Log error, mark bridge as disconnected |
| `RATE_LIMITED` | Return "Agent is busy, please try again shortly" |
| Connection refused | Mark bridge as disconnected, return "Bridge is offline" |

All error messages are user-friendly for voice output. No stack traces, error codes, or technical jargon in conversation responses.

---

## 6. Data Architecture

### Data Models

#### Config Entry Data

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| bridge_url | str | Required, valid URL | Bridge base URL |
| bridge_token | str | Required, non-empty | Bearer token |
| default_agent | str | Required, valid agent ID | Default chat agent |
| voice_agent | str | Optional | Voice-specific agent |
| context_max_chars | int | 1000-200000 | Max entity context chars |
| context_strategy | str | truncate or clear | Overflow handling |
| enable_per_agent_entities | bool | - | Per-agent entities flag |
| enable_tool_calls | bool | - | Tool invocation flag |
| thinking_timeout | int | 10-3600 | Agent response timeout (seconds) |
| ssl_verify | bool | - | SSL certificate verification |
| debug_logging | bool | - | Detailed voice routing logs |

#### CoordinatorData (TypedDict)

```python
class CoordinatorData(TypedDict):
    connected: bool
    bridge_status: str                    # ok, degraded, error
    bridge_version: str
    bridge_uptime: int
    agent_count_healthy: int
    agent_count_total: int
    agents: list[AgentInfo]
    last_poll: str                        # ISO timestamp
```

#### AgentInfo (TypedDict)

```python
class AgentInfo(TypedDict):
    id: str
    name: str
    description: str
    healthy: bool                         # Mapped from discovery: status == "healthy" → True
    adapter: str
    capabilities: dict[str, Any]
    tags: list[str]
```

### Storage Strategy

| Data Type | Storage | Rationale |
|-----------|---------|-----------|
| Config | HA config entry (encrypted `.storage/`) | HA standard, secrets protected |
| Session IDs | HA Store (`.storage/agent_bridge.sessions`) | Survive HA restarts, one per agent |
| Coordinator state | In-memory | Rebuilt from bridge on each poll |
| Conversation history | Bridge channels | Bridge owns persistence |
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
| `agent_bridge_message_received` | Agent responds to conversation | agent_id, model, content_preview, timestamp |
| `agent_bridge_tool_invoked` | Tool invocation completes | agent_id, tool_name, status, duration_ms |
| `agent_bridge_agent_discovered` | New agent appears in discovery | agent_id, name, capabilities |
| `agent_bridge_agent_removed` | Agent disappears from discovery | agent_id, name |

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
    "dependencies": [],
    "documentation": "https://github.com/Engram-Labs-UK/agent-bridge-ha",
    "iot_class": "local_polling",
    "issue_tracker": "https://github.com/Engram-Labs-UK/agent-bridge-ha/issues",
    "requirements": [],
    "version": "0.1.0"
}
```

**Key fields:**
- `config_flow: true` -- enables UI-based setup (Settings > Add Integration)
- `iot_class: local_polling` -- bridge is local network, integration polls for data
- `requirements: []` -- no pip dependencies beyond HA-bundled packages
- `dependencies: []` -- no HA integration dependencies

### HACS Distribution

```json
{
    "name": "Agent Bridge",
    "render_readme": true,
    "homeassistant": "2025.1.0"
}
```

Repository structure for HACS:

```
agent-bridge-ha/
├── custom_components/
│   └── agent_bridge/
│       ├── __init__.py
│       ├── client.py
│       ├── config_flow.py
│       ├── conversation.py
│       ├── coordinator.py
│       ├── exposure.py
│       ├── tool_executor.py
│       ├── helpers.py
│       ├── sensor.py
│       ├── binary_sensor.py
│       ├── event.py
│       ├── services.py
│       ├── const.py
│       ├── manifest.json
│       ├── services.yaml
│       ├── strings.json
│       └── translations/
│           └── en.json
├── tests/
│   ├── conftest.py
│   ├── test_init.py
│   ├── test_client.py
│   ├── test_config_flow.py
│   ├── test_conversation.py
│   ├── test_coordinator.py
│   ├── test_exposure.py
│   ├── test_sensor.py
│   ├── test_binary_sensor.py
│   ├── test_services.py
│   ├── test_tool_executor.py
│   └── test_helpers.py
├── hacs.json
├── CLAUDE.md
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
PLATFORMS = ["sensor", "binary_sensor", "event"]

# Config entry keys
CONF_BRIDGE_URL = "bridge_url"
CONF_BRIDGE_TOKEN = "bridge_token"
CONF_DEFAULT_AGENT = "default_agent"
CONF_VOICE_AGENT = "voice_agent"
CONF_CONTEXT_MAX_CHARS = "context_max_chars"
CONF_CONTEXT_STRATEGY = "context_strategy"
CONF_ENABLE_PER_AGENT = "enable_per_agent_entities"
CONF_ENABLE_TOOL_CALLS = "enable_tool_calls"
CONF_THINKING_TIMEOUT = "thinking_timeout"
CONF_SSL_VERIFY = "ssl_verify"
CONF_DEBUG_LOGGING = "debug_logging"

# Defaults
DEFAULT_CONTEXT_MAX_CHARS = 13000
DEFAULT_CONTEXT_STRATEGY = "truncate"
DEFAULT_THINKING_TIMEOUT = 120
DEFAULT_POLL_INTERVAL = 30           # seconds
DEFAULT_DISCOVERY_INTERVAL = 300     # seconds
DEFAULT_TOOL_TIMEOUT = 10            # seconds per service call
MAX_ENTITIES = 250
MAX_TEXT_DEPTH = 8                   # recursive response text extraction

# Event types
EVENT_MESSAGE_RECEIVED = f"{DOMAIN}_message_received"
EVENT_TOOL_INVOKED = f"{DOMAIN}_tool_invoked"
EVENT_AGENT_DISCOVERED = f"{DOMAIN}_agent_discovered"
EVENT_AGENT_REMOVED = f"{DOMAIN}_agent_removed"

# Response text extraction priority keys
TEXT_PRIORITY_KEYS = ("text", "content", "message", "output_text")
```

### services.yaml

Defines the HA service schemas rendered in the developer tools UI:

| Service | Fields | Required |
|---------|--------|----------|
| `send_message` | message (str), agent_id (str), session_id (str) | message |
| `invoke_tool` | agent_id (str), tool_name (str), args (object) | agent_id, tool_name |
| `broadcast` | message (str), tags (list[str]) | message |

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
| Bridge token leaked in logs | Medium | High | Never log token value; redact in diagnostics |
| Man-in-middle on bridge connection | Low | Medium | SSL/TLS support; warn if ssl_verify=false |
| Malicious agent response (prompt injection) | Low | Medium | Tool execution validates entity_id against exposure list; only exposed entities targetable |
| Rogue tool_call targets sensitive entity | Low | High | Entity validation before execution; only HA-exposed entities can be controlled |
| Excessive entity exposure | Low | Low | 250 entity cap; respects HA expose settings |

### Security Controls

| Control | Implementation |
|---------|----------------|
| Authentication | Bearer token in Authorization header |
| Token storage | HA encrypted config entry (not plaintext) |
| SSL/TLS | Supported with configurable verification |
| Entity access | HA's native expose settings control what agents see |
| Tool call validation | Only exposed entities can be targeted by tool_calls; entity_id checked against exposure list before execution |
| Service call scope | Tool executor only calls HA services (domain.service); no shell execution, no file access, no network calls |

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

### ADR-003: Per-Agent Entities as Opt-In

**Status:** Accepted

**Context:** Should every bridge agent automatically get a conversation entity and health sensor in HA, or should this be opt-in?

**Decision:** Opt-in via `enable_per_agent_entities` option. Default off. The primary conversation agent (routing through bridge default) covers the common case. Per-agent entities add value for multi-satellite setups but create entity clutter for simpler configurations.

**Consequences:**
- Positive: Clean default experience with one conversation agent
- Positive: Power users can enable per-agent control
- Negative: Two-step setup for multi-agent users (enable option, then configure pipelines)

### ADR-004: Entity Exposure from OpenClaw Fork

**Status:** Accepted

**Context:** The OpenClaw HA fork has a battle-tested entity exposure system that formats HA entities with areas, attributes, and caps. Should we rewrite or adapt?

**Decision:** Adapt the OpenClaw fork's `exposure.py` patterns. The formatting logic, attribute selection, area injection, and 250-entity cap are well-proven.

**Consequences:**
- Positive: Proven approach, known to work with voice assistants
- Positive: Faster implementation (adapt, not rewrite)
- Negative: Need to refactor from OpenClaw-specific patterns to generic bridge patterns

### ADR-005: Tool Execution Architecture

**Status:** Accepted

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

---

## 12. Open Technical Questions

- [x] **Q:** Should the integration create a bridge channel per HA conversation ID for multi-turn voice?
  **Context:** Bridge channels persist conversation history. Creating one per HA conversation ID enables multi-turn voice dialogue. But channel cleanup becomes an issue if HA creates many short-lived conversations.
  **Decision:** One session per agent (not per conversation_id), persisted to HA Store. Session ID format: `agent:{agent_id}:assist_{random_hex}`. Sent as `channel` field in chat requests. See PRD Session Persistence feature (EP0002).

- [x] **Q:** How should entity exposure handle template entities and groups?
  **Context:** Template sensors and groups can have complex state. Should they be exposed as-is, or filtered?
  **Decision:** Expose as-is with no type-based filtering. Rationale: (1) Consistent with ADR-001 -- the integration is a thin adapter that respects HA's expose settings, not a second filtering layer. (2) Template entities often contain the most valuable computed state for agents (e.g. `binary_sensor.house_occupied`, `sensor.total_power_draw`). (3) Groups provide relationship context that helps agents handle commands like "turn off everything in the kitchen". (4) The 250-entity cap already prevents prompt bloat. (5) Other HA conversation agents (Google Home, Alexa) follow the same pattern. If a user doesn't want an entity exposed, they un-expose it in HA -- the integration doesn't second-guess.

---

## 13. Implementation Constraints

### Must Have
- Compatible with Home Assistant Core 2025.1.0+
- No additional pip dependencies (only HA-bundled packages)
- HACS-installable repository structure
- Works with Agent Bridge v4.36.0+ REST API (was "v3.1.0+" — corrected 2026-06-01; the v3.1-era contract has drifted, see review banner + CR-0002. Pin + CI against a current HA core per US0029.)
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
