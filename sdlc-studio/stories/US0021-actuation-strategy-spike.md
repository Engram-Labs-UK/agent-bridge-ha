# US0021: Decision spike — validate Option A (HA LLM API/MCP) against live agents

> **Status:** Proposed
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
