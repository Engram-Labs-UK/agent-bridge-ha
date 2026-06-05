# US0037: Proactive announcements to satellites (HA-as-client)

> **Status:** Done — delivered via the agent's `/api/mcp` mount (no new HA listener)
> **Epic:** [EP0008: Conversation Capability Expansion](../epics/EP0008-conversation-capability-expansion.md)
> **Owner:** Darren Benson
> **Created:** 2026-06-05

## User Story

**As a** user
**I want** an agent to proactively speak on a chosen satellite ("washing machine finished")
**So that** the home can notify me without my asking first

## User Story Context

This is the real architecture step: HA must act as a **client** (receive agent→HA pushes), not
just a server. Reuse the existing webhook listener (`webhook.py`) and/or `/v1/messages` callback.
Cora's needs: a specific `assist_satellite` target (not just area), priority levels (don't wake
sleeping rooms), and a way to know which satellites are currently active.

## Acceptance Criteria

### AC1: Announce service
- **Given** a message + target satellite/area + priority
- **When** `agent_bridge.announce` is called
- **Then** HA speaks it via `assist_satellite.announce` (or notify fallback)
- **Verify:** `pytest` asserts the announce service routes to the target satellite

### AC2: Agent→HA inbound trigger
- **Given** an agent push (webhook/callback with an announce intent)
- **When** the bridge delivers it
- **Then** the component handles it and triggers the announce
- **Verify:** `pytest` simulates the inbound push and asserts an announce is issued

### AC3: Priority + active-satellite filtering
- **Given** a priority and satellite availability
- **When** announcing
- **Then** low-priority pushes skip unavailable/quiet satellites; high-priority override per policy
- **Verify:** `pytest` asserts a low-priority push to an unavailable satellite is skipped

## Scope

### In Scope
- `agent_bridge.announce` service; inbound push handler (webhook/callback); satellite targeting
  + priority filtering; active-satellite query
### Out of Scope
- Full duplex / barge-in; the agent→HA trigger *convention* is scoped first with the bridge

## Technical Notes

- Touchpoints: new `proactive.py` + `services.py` + `webhook.py`. Bridge already has webhooks +
  `/v1/messages` callback + broadcast. Define the announce-intent envelope first (small bridge
  convention or a tagged broadcast HA subscribes to).

## Estimation

**Story Points:** 8
**Complexity:** High

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-06-05 | Claude | Initial story for EP0008 (CR-0004), Phase 4 |
| 2026-06-05 | Claude | Implemented `agent_bridge.announce` (target satellite, priority, skip-unavailable-unless-critical) + services.yaml. **Approach refinement vs AC2:** no new HA inbound webhook listener is needed — with Option A the agent already actuates HA via its own `/api/mcp` mount, so it calls this service directly to push speech. This is simpler and avoids a co-requisite bridge convention. "Don't wake sleeping rooms" = skip-if-unavailable for now (DND modelling deferred). Unit-tested. Status → Done |
