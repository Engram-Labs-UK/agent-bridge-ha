# Agent Bridge HA

Home Assistant custom component for Agent Bridge. Exposes bridge agents as HA conversation agents with entity context, voice control, health monitoring, and automation events.

This is the canonical agent-instructions file, read every session (by Claude Code, Codex, Copilot and opencode). `CLAUDE.md` imports it.

## Session start

1. Read `sdlc-studio/reviews/LATEST.md` first - the current-state orientation snapshot. Open it on demand (it is a link, not an auto-import, to keep it out of standing context).
2. Read the operating doctrine once per project: `reference-doctrine.md` in the sdlc-studio skill - the project-agnostic rules this file does not restate.
3. `/sdlc-studio status` for the four pillars; `/sdlc-studio hint` for the next step; `/sdlc-studio lessons recall` before substantive decisions.
4. After any context compaction or reset (`/compact`, `/clear`, or a fresh session), re-read `LATEST.md` and run `/sdlc-studio status` before continuing.

## How to work

- **Think before coding** - state assumptions; surface trade-offs; prefer the boring solution. Ask only when genuinely blocked.
- **Simplicity first** - the minimum that satisfies the story's acceptance criteria; nothing speculative.
- **Surgical changes** - touch only what the story requires; match the existing style.
- **Goal-driven autonomous execution** - run each approved wave through to ship + reconcile. Stop only for a genuine technical blocker the SDLC cannot resolve, an explicit operator pause, or a destructive / hard-to-reverse action. When you need another opinion, **consult instead of stopping** (`/sdlc-studio consult team`). Note: this repo has no `sdlc-studio/personas/` yet, so create them or consult the live fleet before relying on a Persona gate.

## Build and Check

```bash
# Validate Python
python -m py_compile custom_components/agent_bridge/__init__.py
python -m pytest tests/ -v          # pytest (mock the bridge API; never hit a live bridge)
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

## SDLC Studio is the operating system for this repo

Use the `sdlc-studio` skill for every substantive change - even a small bug fix gets a `bug` file (rationale + `Verify:` expression + audit pin). The skill is the source of truth, the audit trail, and the drift-prevention mechanism. Every change flows:

```
CR / Bug  →  Epic  →  Story  →  code plan  →  code implement  →  code verify  →  reconcile  →  review
```

### Daily commands

| Need | Command |
|---|---|
| Where am I? | `/sdlc-studio status` |
| What next? | `/sdlc-studio hint` |
| Plan a story | `/sdlc-studio code plan --story USxxxx` |
| Implement | `/sdlc-studio code implement` *(TDD by default)* |
| Verify AC | `/sdlc-studio reconcile --verify --story USxxxx` |
| File a CR / bug | `/sdlc-studio cr create` / `/sdlc-studio bug create` |
| Fix bookkeeping drift | `/sdlc-studio reconcile` *(idempotent; `--dry-run` to preview)* |
| Unified doc review | `/sdlc-studio review` |

### Discipline gates

- **Query Context7 first** - before writing code that uses any HA library (homeassistant, aiohttp, voluptuous), resolve the library ID and query its docs. Training data may be stale.
- **Follow HA patterns** - DataUpdateCoordinator for polling, ConfigFlow for setup, entity platforms for sensors/binary sensors.
- **Default to TDD** - mock the bridge API; never hit a live bridge in unit tests. Author the failing test / `Verify:` line first → green → refactor.
- **Generated specs MUST be validated by tests** - `prd generate` / `story generate` produce migration blueprints, not documentation; never auto-promote a generated story to Done.

### Pre-release gate (IMPORTANT)

**IMPORTANT - never release until the gate is green.** Before tagging / shipping a HACS update:

1. `/sdlc-studio reconcile --verify` - executes every story's `Verify:` DSL; fails on any `no`/`stale`. This is what makes "Done" mean done.
2. `/sdlc-studio review` across **PRD · TRD · TSD · CODE** (and **Persona once `sdlc-studio/personas/` exists**). The **CODE leg is non-negotiable** - doc review never finds a crash bug, an async-blocking call, or a deploy gap. Fan the legs out as parallel review subagents, triage, and FIX findings before tagging.

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
9. **Keep the tested HA version pinned in both places.** When bumping the supported Home Assistant version, update `const.TESTED_HA_VERSION` AND `HA_VERSION` in `.github/workflows/validate.yml` together (currently `2026.2.3`) — US0029/AC3. CI validates against the pin; drift between the two is a silent break.

## Specifications

Check TRD before implementing -- it has interface definitions, API contracts, and data flow diagrams. PRD has acceptance criteria. All specs in `sdlc-studio/`.

## Current state

Current state lives in `sdlc-studio/reviews/LATEST.md`, rewritten by every `/sdlc-studio review`; read it at session start (see Session start). Older history: `git log` (per-commit narrative) + PRD §11 ChangeLog. Don't reintroduce per-ship narrative into this file.

## Don't

- Don't grow this file with per-ship narrative — that's `git log` + PRD §11 + `LATEST.md`.
- Don't block the event loop — all I/O async; use HA's aiohttp session only (Critical Rules 1, 2, 8).
- Don't hardcode URLs or tokens — everything from the config entry (Critical Rule 6).
- Don't bump HA support in one place only — `const.TESTED_HA_VERSION` and CI `HA_VERSION` move together (Critical Rule 9).
- Don't use a library from memory — query Context7 first.

## Where to look

- **Operator-gated remainder + kickoff:** `sdlc-studio/IMPLEMENTATION-KICKOFF.md` + the EP0007 epic.
- **Spec contract:** PRD (acceptance criteria) · TRD (interfaces + API contracts + data flow) · TSD (test scenarios), all in `sdlc-studio/`.
- **CI:** `.github/workflows/validate.yml` (hassfest / HACS validation on push + PR; HA `2026.2.3` / Python `3.13`).
- **Live CR / bug / story status:** `/sdlc-studio status`.
