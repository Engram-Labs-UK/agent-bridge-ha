# US0030: Document reactive/proactive boundary + update README/TRD to v4.36

> **Status:** Done
> **Epic:** [EP0007: Bridge v4.36 + Modern HA Re-Alignment](../epics/EP0007-bridge-v436-modern-ha-realignment.md)
> **Owner:** Darren Benson
> **Created:** 2026-06-01

## User Story

**As a** future maintainer of agent-bridge-ha
**I want** the reactive vs proactive boundary and the v4.36 contract written down
**So that** the next session boots oriented and the docs stop describing a phantom surface

## User Story Context

G12 context + H7: the now-working proactive path (DBee via `/api/mcp`) overlaps this component's hand-rolled surface; `trd.md:148` documents a phantom `/health?depth=deep` and the README still claims bridge `v3.1.0+`. The boundary between the two non-overlapping paths and the corrected v4.36 contract must be written down. Final reconciliation story for the epic.

## Acceptance Criteria

### AC1: TRD documents the boundary + corrects the surface
- **Given** the HA-side TRD
- **When** updated
- **Then** it documents the two non-overlapping paths (reactive Assist `ConversationEntity` vs proactive MCP Server), corrects the per-agent health surface to `/v1/health` (drops the `depth=deep` illusion), and records how voice metadata reaches the agent (prompt-fold or bridge passthrough, per the decision)
- **Verify:** `grep` asserting `trd.md` no longer documents `depth=deep` as a per-agent surface

### AC2: README states the v4.36 floor
- **Given** the README
- **Then** the bridge-compatibility floor is updated from `v3.1.0+` to the tested `v4.36` baseline
- **Verify:** `grep` asserting README states the v4.36 floor

## Scope

### In Scope
- TRD: reactive vs proactive (MCP Server) boundary
- TRD: correct per-agent health surface to `/v1/health` (drop `depth=deep`)
- TRD: record how voice metadata reaches the agent (prompt-fold or bridge passthrough)
- README: bridge-compatibility floor → v4.36 tested baseline

### Out of Scope
- Code changes (all in US0021–US0029)
- Altering the proactive MCP Server path (DBee) — only documenting the boundary

## Technical Notes

- OQ3 (long-term boundary: does the component cede entity-context/tool exposure to HA's LLM API/MCP, or coexist) and OQ6 (voice-metadata fix: prompt-fold vs bridge passthrough) inform this story's contract notes.
- Depends on US0027 because the documented voice-metadata path and actuation contract follow from the chosen strategy.

## Dependencies

### Story Dependencies

| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| US0027 | Decision | The chosen actuation strategy + metadata path to document | Proposed |

## Estimation

**Story Points:** 2
**Complexity:** Low

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-06-01 | Claude | Initial story for EP0007 (CR-0002 redesign) |
| 2026-06-02 | Claude | R5: TRD boundary + /v1/health correction + README v4.36 floor; grep-verified; status -> Done |
