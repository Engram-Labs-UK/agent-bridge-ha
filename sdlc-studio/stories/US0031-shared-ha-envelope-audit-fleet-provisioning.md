# US0031: Shared HA tool envelope + actuation audit-events + fleet provisioning

> **Status:** Review — component-side done (audit hook + deny/confirm + envelope doc); harness provisioning + audit-mechanism confirmation operator/cross-repo-gated
> **Epic:** [EP0007: Bridge v4.36 + Modern HA Re-Alignment](../epics/EP0007-bridge-v436-modern-ha-realignment.md)
> **Owner:** Darren Benson
> **Created:** 2026-06-01

## R5 Implementation Status (2026-06-02)

In-component pieces landed (R3/R5):
- **AC1 (envelope defined once):** the shared HA tool contract is documented canonically
  in the TRD "Reactive vs Proactive Boundary" section + this story (the `/api/mcp`
  HA-MCP mount, read-before/after-write, deny/confirm list). No per-agent redefinition.
- **AC2 (audit mechanism):** **decision recorded** — reuse the existing bridge audit tool
  **`bridge_mark_critical_audit_event`** (no new `agent-bridge` CR needed); the component
  emits the HA-side `EVENT_ACTUATION_AUDIT` hook each reactive turn (R3). *Operator to
  confirm the bridge-side wiring.*
- **AC4 (safety fleet-wide):** the deny/confirm domain list (`DENY_CONFIRM_DOMAINS`) +
  read-back instruction are folded into the grounding prompt for every agent (R3).

**Operator/cross-repo gated (cannot be done from this repo):**
- **AC3:** provision the shared `/api/mcp` mount into Cora (openclaw) / Eve (codex) /
  Julian (claude-code) harnesses, mirroring DBee's `~/.hermes/config.yaml`.
- **AC2 wiring:** confirm `bridge_mark_critical_audit_event` receives the actuation events.

## User Story

**As a** maintainer of the agent fleet
**I want** the HA actuation capability defined once and provisioned identically across Cora, Eve, and Julian
**So that** every selected voice agent can actuate the home the same way DBee already does, with one shared audit surface — not a per-agent divergence

## User Story Context

US0027 proves the reactive path end-to-end with **DBee** (the only seed agent already `/api/mcp`-mounted). This story generalises that proof to the rest of the seed fleet. Per the US0021 spike + live-fleet consult:
- **HA tools today:** Cora **none** (only openclaw `nodes_*`), Eve **none**, Julian **none**, **DBee yes**. ⇒ the shared HA mount must be **provisioned per harness** (openclaw / codex / claude-code) before those agents can be HA voice agents.
- **Julian (architecture):** define the HA capability **once** as a shared envelope to avoid capability divergence; emit actuation events to the bridge audit log; read-back to confirm.
- **Eve (safety):** per-agent HA credentials, idempotent calls, structured receipts, deny/confirm list.

This is the cross-repo / cross-harness counterpart to US0027's in-component proof. Much of it is **operator-gated** (harness provisioning is not codeable from this repo) and **cross-repo** (the audit-event mechanism may need a small `agent-bridge` CR).

## Acceptance Criteria

### AC1: Shared HA tool envelope defined once
- **Given** multiple agents will actuate HA
- **When** the capability is defined
- **Then** there is a single shared HA tool envelope (capability contract: the `/api/mcp` HA MCP Server mount + its tool surface + read-before/after-write convention + deny/confirm list) documented as the source of truth, not redefined per agent
- **Verify:** the envelope is documented in one place (story/TRD/`sdlc-studio/decisions`) and referenced by each harness config; `grep` finds a single canonical definition

### AC2: Actuation audit-event mechanism decided and wired
- **Given** an actuation occurs during a reactive turn
- **When** it completes
- **Then** it emits an event to the bridge audit log via a decided mechanism — either an existing bridge audit tool (e.g. `bridge_mark_critical_audit_event`) or a small dedicated `agent-bridge` CR — with the choice recorded
- **Verify:** the decision is recorded; an actuation produces an audit-log entry observable on the bridge

### AC3: Cora, Eve, Julian provisioned with the shared mount
- **Given** the shared envelope and a per-harness config
- **When** Cora (openclaw), Eve (codex), and Julian (claude-code) are provisioned
- **Then** each mounts `homeassistant` at `http://10.0.0.209:8123/api/mcp` (Streamable HTTP, `Bearer ${HASS_TOKEN}`, per-agent credentials) mirroring DBee's `~/.hermes/config.yaml`, and each can actuate + read-back
- **Verify:** operator confirms each of the three agents performs a 'turn on the lights' actuation with confirmation (logged per agent); operator-gated

### AC4: Safety + idempotency honoured fleet-wide
- **Given** the deny/confirm list and idempotent-call requirement
- **When** any provisioned agent actuates
- **Then** risky domains (locks/alarms/heating/external doors) are gated, calls are idempotent, and receipts are structured
- **Verify:** the deny/confirm list and idempotency convention are part of the shared envelope and exercised in the per-agent E2E

## Scope

### In Scope
- The single shared HA tool envelope / capability contract (define once)
- The actuation audit-event mechanism decision + wiring (reuse bridge audit tool vs small `agent-bridge` CR)
- Provisioning the shared `/api/mcp` mount into Cora / Eve / Julian harnesses (operator-gated)
- Fleet-wide deny/confirm list + per-agent credentials + idempotent calls + structured receipts

### Out of Scope
- The in-component DBee-first reactive proof (**US0027**)
- The `ConversationEntity`/`ChatLog` platform itself (US0025/US0026)
- Per-agent TTS voice selection / wake-word training

## Technical Notes

- **Operator/cross-repo gated:** harness provisioning (openclaw/codex/claude-code) and the audit mechanism (possible `agent-bridge` CR) are not codeable from `agent-bridge-ha`. This story coordinates and documents them; only the in-component pieces (envelope reference, audit hook point) land here.
- Mirror DBee's working config: `mcp_servers.homeassistant` → `url: http://10.0.0.209:8123/api/mcp`, Streamable HTTP, `Bearer ${HASS_TOKEN}`.
- Cross-repo CR-number collision is a known hazard — compare contracts, not numbers (per US0021 notes).
- Resolves OQ3 (component-vs-`/api/mcp` boundary) in the "yes, cede tool exposure to the mount" direction for the seed fleet.

## Dependencies

### Story Dependencies

| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| US0027 | Proof | DBee-first reactive proof + the in-component audit hook point | Proposed |
| US0025 | Platform | In-app agent selection (config subentries) for Cora/Eve/Julian/DBee | Proposed |

### Operator / External Dependencies

| Dependency | What's Needed | Owner |
|------------|---------------|-------|
| Harness provisioning | Mount shared `/api/mcp` into Cora (openclaw), Eve (codex), Julian (claude-code) | Operator |
| Audit mechanism | Decide reuse `bridge_mark_critical_audit_event` vs small `agent-bridge` CR | Operator + agent-bridge |

## Estimation

**Story Points:** 5
**Complexity:** High (cross-repo + operator coordination)

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-06-01 | Claude | Created in R0 reconcile per US0021 spike outcome (fleet envelope + audit-events + provisioning split out of US0027) |
