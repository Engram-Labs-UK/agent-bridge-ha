# Agent Bridge HA

Home Assistant custom component for Agent Bridge. Exposes bridge agents as HA conversation agents with entity context, voice control, health monitoring, and automation events.

## Build and Check

```bash
# Validate Python
python -m py_compile custom_components/agent_bridge/__init__.py
python -m pytest tests/ -v          # pytest (when test suite exists)
ruff check custom_components/       # lint
ruff format custom_components/      # format
mypy custom_components/             # type check
```

All checks must pass before merge.

## Architecture

HA custom component that acts as a thin adapter between Home Assistant's conversation/entity framework and the Agent Bridge REST API.

```
Voice Satellite / Assist UI / Automation
        |
HA Conversation Agent (per bridge agent)
        |
Entity Exposure (formats HA state for AI context)
        |
Bridge Client (aiohttp) ──► POST /v1/chat/completions
        |                          |
        |                    Agent responds with tool_calls
        |                          |
Tool Executor ◄───────────── execute_service(light.turn_on, light.kitchen)
        |
hass.services.async_call() ──► Actual device control
        |
Tool result sent back to agent ──► Final spoken response
```

**Design principles:** thin adapter (bridge owns routing, resilience, discovery), HA-native patterns (DataUpdateCoordinator, config flow, entity platforms), no duplication of bridge logic. Tool execution is the critical path -- without it agents describe actions but cannot perform them.

## Config

Configured via HA UI (Settings > Devices & Services > Add Integration > Agent Bridge). Stores bridge URL, token, and agent preferences in HA config entry. No config files to manage.

## Development Workflow

1. **Query Context7 first** -- before writing code that uses any HA library (homeassistant, aiohttp, voluptuous), resolve the library ID and query its docs.
2. **Follow HA patterns** -- use DataUpdateCoordinator for polling, ConfigFlow for setup, entity platforms for sensors/binary sensors.
3. **Test with pytest** -- mock the bridge API responses, never hit a live bridge in unit tests.

## Critical Rules

These cause real bugs if ignored:

1. **All I/O is async** -- use `aiohttp` for HTTP, never `requests`. All HA methods are `async def`.
2. **Never block the event loop** -- no synchronous HTTP calls, no `time.sleep()`, no blocking file I/O.
3. **Entity exposure is the key feature** -- without it, agents cannot understand the home. Always include entity state context in conversation prompts.
4. **Tool execution is how agents control the home** -- agents return `tool_calls` in their response, the integration executes them via `hass.services.async_call()`, and sends results back. Only exposed entities can be targeted.
5. **Bridge is the routing layer** -- HA sends `agent` field in chat requests, bridge handles failover/circuit breaking. HA does not replicate bridge resilience logic.
6. **No hardcoded URLs or tokens** -- everything from config entry data.
7. **British English** in all comments, docs, and user-facing strings.
8. **Use HA's aiohttp session** -- `async_get_clientsession(hass)`, never create your own `aiohttp.ClientSession`.

## Specifications

Check TRD before implementing -- it has interface definitions, API contracts, and data flow diagrams. PRD has acceptance criteria. All specs in `sdlc-studio/`.

## Current State

Brownfield, **0.9.0** released. 0.9.0 (EP0008 Phase 6, US0039) adds an **AI Task platform**: one
`ai_task` entity per agent so automations/dashboards/templates can call `ai_task.generate_data`
for a summary or structured JSON (scoped — no image gen / schema registry). 0.8.0 (EP0008 Phase 4,
US0037) adds **proactive announcements**:
the `agent_bridge.announce` service speaks a message on a chosen `assist_satellite` with a
priority (low/normal skip an unavailable satellite; critical always attempts). With Option A the
agent triggers it via its own `/api/mcp` mount — no new HA listener. 0.7.0 (EP0008 Phase 2+3)
adds **camera/vision input**
(`agent_bridge.ask_with_image` sends a camera snapshot as an image attachment, US0035) and
**confirm-before-actuate** (US0036): the agent prefixes a safety confirmation with
`[confirm:LEVEL]`, which HA strips from speech, surfaces as `severity`/`awaiting_confirmation`
on its events, and keeps the conversation open for the user's yes/no. 0.6.0 (EP0008 Phase 1b+1c)
adds **opt-in response streaming**
to TTS (US0033, `CONF_ENABLE_STREAMING`, default off, fallback-safe) and a **richer grounding
envelope** (US0034): recently-changed entities, presence/"who's home", and next alarm/calendar,
folded into the caller_context source block. 0.5.0 (EP0008 Phase 1, US0032) adds **session
continuity**:
the bridge already persists a session per `channel` (24h TTL, confirmed by the Phase 0 spike),
so the conversation entity now sends an **idle-windowed channel key** `ha:{agent_id}:{scope}:{epoch}`
(scope = device → user → default) instead of the ephemeral `conversation_id`. Consecutive turns
within `CONF_SESSION_IDLE_WINDOW` (default 600 s) share context; a longer gap or a backwards clock
jump rotates the key. The per-entity epoch map is UTC-based and prunes scopes past the 24h TTL.
0.4.0 added a structured speaker/source/location envelope:
each turn now carries a `caller_context` (source type voice/text/automation, device/speaker
name, area + floor, language, local time, best-effort unverified account) rendered into the
system prompt as a labelled `[home-assistant-source]` block and sent as a `caller_context`
body field (replacing the old, bridge-dropped `metadata`). The bridge half (accept +
`injectSourceHint` + journal record) lives in agent-bridge `feat/caller-context-passthrough`;
the HA prompt-inlining delivers the agent-facing benefit without it. EP0007 / CR-0002
(re-align to bridge v4.36 + modern HA)
implemented across R1-R5 (248 tests green on HA 2026.2.3 / Python 3.13) at 0.2.0; CR-0003 /
BG0003 (crew-scoped agent picker + editable HA-origin instructions) shipped in 0.3.0, with the
0.3.1 crew-projection fix (`?include=crew`). 0.3.2 fixes BG0004: the default
`x-bridge-mcp-caller` (`homeassistant`) is not a registered bridge agent, so v4.36 rejected
every conversation turn with 403; `caller_id` now resolves to the configured agent (operator
override in options) and caller-identity denials are reported distinctly from token failures.
261+ tests green:
- **Reactive path** re-platformed onto `ConversationEntity` + `ChatLog` (one entity per agent via
  config subentries); legacy `AbstractConversationAgent`/`async_set_agent` deleted.
- **Actuation** = Option A refined: the entity forwards the utterance + a grounding hint as free
  text; the agent actuates HA itself via its own `/api/mcp` mount (not an `llm.Tool` round-trip).
  Deny/confirm list + fail-closed exposure + an `EVENT_ACTUATION_AUDIT` hook are in place.
- **v4.36 contract**: invoke/broadcast/SSE/webhook shapes, `x-bridge-mcp-caller`, health/metrics/
  taxonomy capture, `/v1/health` tri-state, `bridge:upgraded` → drift repair issue, CI vs pinned HA.

**Operator-gated remainder** (cannot be done from this repo): US0021 live reactive-turn logs;
US0027 live "turn on the lights" E2E on the live HA (10.0.0.209); US0031 provisioning the shared
`/api/mcp` mount into Cora/Eve/Julian harnesses + confirming the bridge audit-event wiring.
See `sdlc-studio/IMPLEMENTATION-KICKOFF.md` and the EP0007 epic.

---

*Version: 0.9.0 -- 2026-06-05 (EP0008 Phase 6 / US0039 AI Task platform; EP0007 operator live-E2E + fleet provisioning still pending)*
