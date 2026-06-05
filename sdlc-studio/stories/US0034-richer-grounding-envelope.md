# US0034: Richer grounding — recent changes + presence + alarms/calendar

> **Status:** Proposed
> **Epic:** [EP0008: Conversation Capability Expansion](../epics/EP0008-conversation-capability-expansion.md)
> **Owner:** Darren Benson
> **Created:** 2026-06-05

## User Story

**As a** bridge agent serving the home
**I want** recent state changes, who's home, and upcoming alarms/calendar in the turn envelope
**So that** I answer diagnostically ("why is it so hot?") and gate safety by who is present

## User Story Context

Cora asked for three additions beyond 0.4.0 caller_context: recent *changes* at turn start,
a presence/"who's home" signal, and upcoming alarms/calendar context.

## Acceptance Criteria

### AC1: Recent state changes
- **Given** exposed entities that changed shortly before the turn
- **When** building grounding
- **Then** a concise "recently changed" section lists entity, old→new, and rough age
- **Verify:** `pytest` asserts a recently-changed entity appears with old→new and is bounded in size

### AC2: Presence / who's-home
- **Given** person/presence entities
- **When** building caller_context
- **Then** a `presence` summary (who is home) is included, privacy-bounded
- **Verify:** `pytest` asserts presence reflects home/away person states

### AC3: Upcoming alarms/calendar
- **Given** next alarm and near-term calendar events
- **When** building caller_context
- **Then** a compact `upcoming` hint is included (best-effort; omitted if unavailable)
- **Verify:** `pytest` asserts next-alarm/calendar hint present when entities exist, absent otherwise

### AC4: Size + privacy bounds
- **Given** the additions
- **When** assembled
- **Then** total grounding respects the existing char budget and excludes secrets/MAC/IP
- **Verify:** `pytest` asserts the budget cap still holds

## Scope

### In Scope
- Extend `exposure.py` (recent changes) + caller_context builder (presence, alarms/calendar)

### Out of Scope
- Full history/timeline; long-term memory (agent owns that)

## Technical Notes

- Recent changes: state machine `last_changed`/`last_updated`; bound to N most recent exposed.
- Presence: `person.*` / device_tracker home/away. Alarms: next `sensor.*_next_alarm` or
  `alarm`/`timer`; calendar: `calendar.*` upcoming. All best-effort + budget-bounded.

## Estimation

**Story Points:** 5
**Complexity:** Medium

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-06-05 | Claude | Initial story for EP0008 (CR-0004), Phase 1c |
