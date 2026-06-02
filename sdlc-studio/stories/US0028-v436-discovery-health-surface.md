# US0028: Adopt v4.36 discovery/health surface (caller header, health, metrics, taxonomy, `/v1/health`)

> **Status:** Done
> **Epic:** [EP0007: Bridge v4.36 + Modern HA Re-Alignment](../epics/EP0007-bridge-v436-modern-ha-realignment.md)
> **Owner:** Darren Benson
> **Created:** 2026-06-01

## User Story

**As a** Home Assistant operator
**I want** the integration to consume the v4.36 discovery + health surface
**So that** entities are capability-gated, health is honest (state/circuit/staleness/metrics), and crew-aware selection works

## User Story Context

G8/G9/G14/G15/G17/G18: the component consumes a v3.1-era subset. Sending `x-bridge-mcp-caller` unlocks crew-aware selection and `include=` projections; capturing the CR-0097 health block, CR-0245 metrics and CR-0256/0247/0259 taxonomy enables capability-driven entity gating and honest backing transparency; `/v1/health` adds a tri-state + `toolSurface` view that directly diagnoses actuation mismatches. Today a busy, open-circuit, stale agent all read identically and Workerbots/orchestrators get exposed as voice agents indiscriminately.

## Acceptance Criteria

### AC1: Send `x-bridge-mcp-caller`
- **Given** any discovery/chat call
- **When** sent
- **Then** it includes an `x-bridge-mcp-caller` header from a configurable caller identity
- **Verify:** `pytest` asserting the caller header is present on `discover()`

### AC2: Capture the full health block + metrics + taxonomy
- **Given** discovery
- **When** parsed
- **Then** `AgentInfo` captures `health.state`/`circuit`/`inflight`/`lastSeenAt`/`staleAfter`, `metrics.latency`/`requests`/`errors`, and `agentClass`/`capabilityEnvelope`/`isOrchestrator`/`framework`/`effectiveModel`/`modelProvider`/`deprecated`
- **Verify:** `pytest` asserting a busy/open-circuit agent yields distinct sensor state from healthy

### AC3: Gate entity creation on `capabilityEnvelope`
- **Given** entity creation
- **When** deciding which agents become voice entities
- **Then** it gates on `capabilityEnvelope` (e.g. Chatbot/Agent, not Workerbot/orchestrator) rather than `capabilities.chat` alone
- **Verify:** `pytest` asserting a Workerbot is not exposed as a voice entity

### AC4: Poll auth-gated `/v1/health` with tri-state + toolSurface
- **Given** health polling
- **When** run
- **Then** the per-agent poll uses the auth-gated `/v1/health`, mapping the tri-state `bridge` field to a `BridgeStatusSensor` that has a `'warning'` state, and surfacing `toolSurface` + `readOnlySafe` as attributes
- **Verify:** `pytest` asserting the `warning` tri-state maps to a distinct sensor state and `toolSurface`/`readOnlySafe` appear as attributes

## Scope

### In Scope
- `x-bridge-mcp-caller` header from a configurable caller identity
- `AgentInfo` capture of CR-0097 health block + CR-0245 metrics + CR-0256/0247/0259 taxonomy
- `capabilityEnvelope`-gated voice-entity creation
- `/v1/health` tri-state + `toolSurface`/`readOnlySafe` adoption; `BridgeStatusSensor` `warning` state

### Out of Scope
- `?agent=&include=` projection optimisation beyond what the caller header unlocks (low-priority follow-on)
- Drift-detection consumer (US0029)

## Technical Notes

- `/health?depth=deep` is a phantom (the handler ignores the query string); per-agent readiness lives at the auth-gated `/v1/health` (CR-0160).
- Choosing a caller identity that maps to no crew could over- or under-expose agents (crew filtering is caller-gated) — needs OQ4 operator input.
- Surfacing `toolSurface` directly diagnoses the actuation gap (advertised-vs-wired).

## Dependencies

### Story Dependencies

| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| US0025 | Platform | Per-agent entities to gate on `capabilityEnvelope` | Proposed |

## Estimation

**Story Points:** 5
**Complexity:** Medium

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-06-01 | Claude | Initial story for EP0007 (CR-0002 redesign) |
| 2026-06-02 | Claude | R4 implemented + unit-tested (248 green); status -> Done |
