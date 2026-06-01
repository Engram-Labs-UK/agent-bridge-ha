# US0021: Decision spike — validate Option A (HA LLM API/MCP) against live agents

> **Status:** In Progress — decision RECORDED 2026-06-01 (live-fleet consult complete); AC2 live-trace pending operator HA logs
> **Epic:** [EP0007: Bridge v4.36 + Modern HA Re-Alignment](../epics/EP0007-bridge-v436-modern-ha-realignment.md)
> **Owner:** Darren Benson
> **Created:** 2026-06-01

## User Story

**As a** maintainer of agent-bridge-ha
**I want** the actuation strategy decided and validated against live agents before building
**So that** the load-bearing re-platform (US0027) is built on a confirmed fork, not a guess

## User Story Context

Resolves OQ1, the fork everything downstream depends on. Heterogeneous bridge agents (Cora/Spanners run their own harness identity) may not speak HA's `llm.Tool` schema, while the bridge currently offers no `tools[]`/`tool_calls` passthrough at all. A short spike with the operator's live HA logs and one live agent over the bridge decides between (A) HA-native LLM API / MCP delegation and (B) the two-sided OpenAI `tool_calls` fix. CR-0002 records Option A as the chosen direction; this story validates that decision against the live fleet (live-agent consult is mandatory).

## Acceptance Criteria

### AC1: Written strategy decision recorded
- **Given** the spike is run
- **When** complete
- **Then** a written decision records which strategy is chosen and why; for Option B, a linked `agent-bridge` CR for the `tools[]`/`tool_calls` passthrough (`chat.ts` `ChatRequestBody` + `RouterRequest`/`SendOptions` + the http-openai adapter outbound body); for Option A, confirmation that the target live agents can be reached via HA's LLM-API tool surface
- **Verify:** `grep -i "chosen strategy\|Option A\|Option B" sdlc-studio/stories/US0021-actuation-strategy-spike.md`

### AC2: Live trace captured
- **Given** a live Cora/Spanners reactive turn today
- **When** captured
- **Then** the trace shows whether `tool_calls` are ever emitted today (free text vs `tool_calls` vs empty/`x_bridge.outbound.empty` vs wrong tool name), pinning which symptom (OQ2) dominates and validating the chosen fix before build
- **Verify:** the spike notes contain a captured live-turn trace excerpt

## Scope

### In Scope
- Operator-supplied live HA reactive-turn logs (OQ2)
- One live-agent consult over the bridge to confirm `llm.Tool` reachability (Option A)
- A recorded decision section (in this story or `sdlc-studio/decisions`)

### Out of Scope
- Building the actuation fix (US0027)
- Any code change

## Technical Notes

- Per CR-0002 the preferred direction is Option A: delegate entity context + tools to HA's Assist LLM API / MCP Server (converges with the working DBee proactive path, removes cross-repo schema risk).
- Option B would require a co-requisite `agent-bridge` CR; cross-repo CR-number collision is a known hazard — compare contracts, not just numbers.
- Live-agent consult is mandatory for agent-facing design per project directive.

## Spike Outcome (2026-06-01 — decision recorded; live-fleet consult complete)

**Strategy: Option A confirmed — HA-native actuation**, refined by the consult to the **agent-direct + shared-envelope + audit-event** model. This is NOT the "conversation entity hands `llm.Tool` to the agent-as-LLM" pattern — that **cannot** work here, because the v4.36 bridge carries no `tool_calls`, so HA's LLM API cannot round-trip tools through the bridge agent.

**Decided design**
1. The agent-bridge-ha **ConversationEntity** receives the HA Assist utterance + a compact entity **grounding hint** (names/areas/aliases — a *hint, not state authority*), forwards it as **free text** to the selected bridge agent (no `tool_calls` on the bridge), and returns the agent's reply to HA Assist.
2. **The agent actuates HA directly** during its turn via a **shared HA tool contract** mounted identically in each selected agent's harness — the **DBee `/api/mcp` (HA MCP Server) pattern**. Agents **read live state before/after** to close the loop (no actuation they can't confirm — EP0095 verification surface).
3. Each actuation **emits an event to the bridge audit log** (one audit surface; honours Rule 3 — no MessageRouter bypass *for effects*). Via an existing bridge audit tool or a small `agent-bridge` CR (TBD by the new session).
4. A **deny/confirm list** gates safety-relevant domains (locks, alarms, heating, external doors).

**Live-fleet consult (mandatory gate) — Cora, Eve, Julian (DBee already mounted)**
- **HA tools today:** Cora **none** (only openclaw `nodes_*`), Eve **none**, Julian **none**, **DBee yes** (`/api/mcp`, live-verified 2026-06-01). ⇒ the shared HA mount must be **provisioned per harness** (openclaw / codex / claude-code) before those agents can be HA voice agents.
- **All three:** treat prompt context as a grounding **hint**, not authority; **live read-before-write** non-negotiable.
- **Julian (architecture):** define the HA capability **once** as a shared envelope (avoid capability divergence across agents) + **emit actuation events to the bridge audit log** + read-back to confirm.
- **Eve (safety):** per-agent HA credentials, idempotent calls, structured receipts, deny/confirm list.

**Rollout:** **DBee-first** — prove the reactive path end-to-end with the already-mounted DBee, then provision + add Cora/Eve/Julian.
**Agent selection:** in-app (HA config UI / US0025 subentries), operator-selectable; seed set = **Cora, Eve, Julian, DBee**.
**Follow-on story to create:** **US0031 — Shared HA tool envelope + actuation audit-events + fleet provisioning** (shared `/api/mcp` mount across Cora/Eve/Julian + the bridge audit-event path). US0027 covers the DBee-first reactive proof.
**AC2 open:** operator's live HA reactive-turn logs (OQ2) to confirm the dominant failure symptom.

## Dependencies

### Story Dependencies

| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| — | — | No story dependency (needs operator live HA logs) | — |

## Estimation

**Story Points:** 2
**Complexity:** Medium

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-06-01 | Claude | Initial story for EP0007 (CR-0002 redesign) |
