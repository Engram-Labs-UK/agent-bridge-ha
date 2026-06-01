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

Brownfield. v0.1.0 shipped (EP0001-EP0006, US0001-US0020 Done): full component under
`custom_components/agent_bridge/` with a pytest suite under `tests/`. Now executing **EP0007 /
CR-0002** (target 0.2.0): re-align to bridge v4.36 + modern HA (`ConversationEntity` + `ChatLog`)
and restore the reactive actuation path, which is currently structurally inert (agents reply but
never actuate). Actuation design = **Option A refined**: the conversation entity forwards the
utterance + a grounding hint as free text and the agent actuates HA itself via a shared `/api/mcp`
mount (the DBee pattern) — not an `llm.Tool` round-trip. See `sdlc-studio/IMPLEMENTATION-KICKOFF.md`.

---

*Version: 0.1.0 -- 2026-04-05 (EP0007 in flight toward 0.2.0)*
