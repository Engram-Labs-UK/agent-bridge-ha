# US0027: Restore reactive actuation — DBee-first proof (agent-direct) + fail-closed exposure

> **Status:** Proposed
> **Epic:** [EP0007: Bridge v4.36 + Modern HA Re-Alignment](../epics/EP0007-bridge-v436-modern-ha-realignment.md)
> **Owner:** Darren Benson
> **Created:** 2026-06-01

## User Story

**As a** Home Assistant voice user
**I want** "turn on the lights" to actually actuate a device again
**So that** the reactive home-control path stops being structurally inert (agents reply but never act)

## User Story Context

G1/G4: the load-bearing fix. This story also fixes the fail-open exposure bare-except (`exposure.py:125-127` returns True on import failure, exposing ALL entities).

> **⚠️ DECIDED DESIGN (2026-06-01, from the US0021 spike + live-fleet consult — supersedes the Option-A/B framing in AC1 below).** "Option A / HA-native" in practice = **agent-direct actuation via a shared HA mount**, NOT the conversation-entity-provides-`llm.Tool` pattern (that needs the bridge to round-trip `tool_calls`, which it does not do). The decided model:
> 1. This **ConversationEntity** forwards the HA Assist utterance + a compact entity **grounding hint** (hint, not authority) as **free text** to the selected bridge agent, and returns the reply — it does **not** itself actuate.
> 2. **The agent actuates HA directly** via a **shared HA tool contract** mounted identically per harness (the DBee `/api/mcp` HA MCP Server pattern), with **live read-back** to confirm.
> 3. Each actuation **emits an event to the bridge audit log** (one audit surface, Rule 3).
> 4. **Deny/confirm list** for risky domains (locks/alarms/heating/external doors).
> 5. **`exposure.py` + `tool_executor.py` are RETIRED** (entity context + tools move to the agent's HA mount) — the fail-closed fix (AC2) applies only while they remain during transition.
> 6. **DBee-first** (already mounted); provisioning Cora/Eve/Julian + the shared-envelope/audit-event path is the new **US0031** (to create). AC1 below is reframed accordingly: this story = the DBee-first reactive proof (free-text forward + grounding hint + reply + actuation-audit surfacing), not a bridge `tool_calls` round-trip.

## Acceptance Criteria

> Per the US0021 spike + live-fleet consult, this story is the **DBee-first reactive proof** of the refined Option A (agent-direct actuation via a shared HA mount). It does **not** wire `async_provide_llm_data()`/`llm.Tool` — the bridge carries no `tool_calls`, so HA's LLM API cannot round-trip tools through the bridge agent. The fleet-wide envelope + audit-event path + Cora/Eve/Julian provisioning live in **US0031**.

### AC1: Reactive turn forwards utterance + grounding hint as free text
- **Given** a reactive HA Assist turn for a selected bridge agent
- **When** the entity handles it
- **Then** it forwards the utterance plus a compact entity **grounding hint** (exposed names/areas/aliases — a hint, not state authority) as **free text** to the bridge agent (no `tools[]`/`tool_calls` on the bridge), and returns the agent's reply to HA Assist via `ChatLog`
- **Verify:** `pytest` asserts a reactive turn sends a free-text message containing the grounding hint and returns the agent reply through `ChatLog` (no `tools[]` in the outbound chat body)

### AC2: Actuation proven end-to-end against DBee (already `/api/mcp`-mounted)
- **Given** DBee selected as the HA voice agent and a 'turn on the lights' utterance
- **When** DBee actuates HA itself via its mounted `/api/mcp` HA tool surface and reads state back to confirm
- **Then** the device changes state and the confirmation is reflected in the spoken reply — proving the reactive path is no longer structurally inert
- **Verify:** operator manual E2E on the live HA (10.0.0.209) captures the device actuating + confirmation in the reply (logged in the story); unit `pytest` asserts the free-text forward + reply round-trip the entity correctly

### AC3: Actuation surfaced to the bridge audit log
- **Given** an actuation occurs during a reactive turn
- **When** the turn completes
- **Then** the actuation is surfaced to the bridge audit log (one audit surface, Rule 3) — via the mechanism decided in US0031 (existing bridge audit tool vs a small `agent-bridge` CR)
- **Verify:** the reactive proof records an audit entry for the actuation (or, until US0031 lands the mechanism, documents the audit hook point the component emits to)

### AC4: Exposure fails closed
- **Given** an entity-exposure import failure (while `exposure.py` remains during transition)
- **When** `_is_entity_exposed` runs
- **Then** it fails CLOSED (skip the entity), never expose-all
- **Verify:** `pytest` asserting exposure fails closed on `ImportError`

## Scope

### In Scope
- Free-text forward of utterance + entity **grounding hint** to the selected bridge agent (DBee-first), reply returned via `ChatLog`
- DBee-first end-to-end actuation proof (agent actuates via its own `/api/mcp` mount, reads state back)
- Actuation surfaced to the bridge audit log (mechanism per US0031)
- Deny/confirm gating for risky domains (locks/alarms/heating/external doors) honoured on the proof path
- Fail-closed `_is_entity_exposed` on import failure (while `exposure.py`/`tool_executor.py` remain during transition)

### Out of Scope
- Fleet-wide shared HA tool envelope + audit-event path + provisioning Cora/Eve/Julian (**US0031**)
- `async_provide_llm_data()`/`llm.Tool` round-trip (ruled out by the spike — bridge has no `tool_calls`)
- Per-agent TTS voice selection / wake-word training
- Replacing the proactive MCP Server path (DBee) — boundary documented in US0030, not altered here

## Technical Notes

- Decided design source: US0021 Spike Outcome (2026-06-01) + live-fleet consult. The conversation entity is the Assist front-end (voice/picker/grounding hint); the **agent** owns actuation via its harness-mounted HA tool surface, with **live read-before/after-write** non-negotiable.
- DBee-first because it is the only seed agent already `/api/mcp`-mounted (Cora/Eve/Julian have no HA tools today — provisioned in US0031).
- Fail-closed must be a deliberate, logged fallback — not silent expose-all OR silent expose-none.
- AC2's live E2E gates the release tag (`0.2.0-beta1`); it cannot be satisfied from this session (live HA is password-auth, not reachable here) — operator-run.

## Dependencies

### Story Dependencies

| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| US0026 | Platform | `_async_handle_message` + `ChatLog` to carry the free-text forward + reply | Proposed |
| US0021 | Decision | AC2 live-trace (operator HA logs, OQ2) confirming the dominant failure symptom before freezing | In Progress |
| US0031 | Follow-on | Decides the audit-event mechanism (AC3) + fleet envelope; DBee proof can land first | Proposed |

## Estimation

**Story Points:** 8
**Complexity:** High

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-06-01 | Claude | Initial story for EP0007 (CR-0002 redesign) |
| 2026-06-01 | Claude | R0 reconcile: retitled + ACs/Scope/Notes rewritten to the refined Option A (agent-direct, DBee-first); split fleet envelope/audit-mechanism/provisioning out to US0031; dropped `async_provide_llm_data`/`llm.Tool` as primary path |
