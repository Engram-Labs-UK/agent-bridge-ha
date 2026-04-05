# EP0006: Advanced Voice

> **Status:** Done
> **Owner:** Darren Benson
> **Reviewer:** --
> **Created:** 2026-04-05
> **Target Release:** 0.2.0

## Summary

Phase 2 voice enhancements: SSE streaming for lower-latency responses (first words sooner) and continuation detection for multi-turn voice dialogue (agent asks follow-up, HA keeps listening).

## Inherited Constraints

| Source | Type | Constraint | Impact |
|--------|------|------------|--------|
| TRD | Architecture | SSE streaming is optional, falls back to non-streaming | Must not break existing conversation flow |
| PRD | Performance | Streaming timeout 300s (separate from thinking_timeout) | Separate timeout configuration |

---

## Business Context

### Problem Statement
Voice responses require waiting for the complete agent response before any audio plays. Multi-turn dialogue requires manually re-activating the satellite.

**PRD Reference:** [SSE Streaming](../prd.md#sse-streaming)

### Value Proposition
Streaming makes voice feel snappier. Continuation detection makes multi-turn conversation natural.

### Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Time to first audio word | Full response time | < 2s after agent starts | E2E voice test |
| Multi-turn success | Manual reactivation | Automatic continuation | E2E voice test |

---

## Scope

### In Scope
- Bridge client SSE streaming mode (stream=True in chat request)
- Async iterator for content deltas
- Conversation agent streaming assembly
- Fallback to non-streaming on SSE failure
- Continuation detection (question pattern analysis in conversation.py)

### Out of Scope
- Streaming for non-voice (text) requests
- Custom continuation phrase UI (configured via options flow only)

### Affected Personas
- **Voice satellite users:** Faster responses, natural multi-turn dialogue

---

## Acceptance Criteria (Epic Level)

- [x] Bridge client supports SSE streaming from chat completions
- [x] Streaming falls back to non-streaming on failure
- [x] Partial content assembled into complete ConversationResult
- [x] Streaming timeout configurable (default 300s)
- [x] Continuation detection triggers on final sentence ending with ? plus continuation phrases
- [x] Continuation suppressed for exclusion phrases (rhetorical questions)
- [x] Both phrase lists configurable via options
- [x] ruff lint, ruff format, and mypy pass with zero errors

---

## Dependencies

### Blocked By

| Dependency | Type | Status | Owner |
|------------|------|--------|-------|
| EP0001 | Epic | Done | Darren Benson |
| EP0002 | Epic | Done | Darren Benson |

### Blocking

| Item | Type | Impact |
|------|------|--------|
| None | -- | -- |

---

## Risks & Assumptions

### Assumptions
- Bridge supports SSE streaming for chat completions (stream=True parameter)
- HA ConversationResult supports continue_conversation flag in 2025.1.0+

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Bridge SSE format differs from OpenAI standard | Low | Medium | Test with actual bridge output |
| Continuation detection false positives | Medium | Low | Configurable exclusion list, conservative defaults |

---

## Technical Considerations

### Architecture Impact
Extends bridge client with async iterator pattern. Extends conversation agent with streaming assembly and continuation detection.

### Integration Points
- Bridge Client streaming mode (from EP0001)
- Conversation Agent (from EP0002)
- HA ConversationResult.continue_conversation flag

---

## Sizing

**Story Points:** 5
**Estimated Story Count:** 2

**Complexity Factors:**
- SSE parsing (chunked async iteration)
- Streaming fallback logic
- Continuation phrase matching (case-insensitive, configurable)

---

## Story Breakdown

| | ID | Title | Status | Points |
|---|-----|-------|--------|--------|
| [x] | [US0020](../stories/US0020-sse-streaming.md) | SSE Streaming | Done | 5 |

**Total:** 1 story, 5 points

**Note:** Continuation Detection was implemented in Phase 1 (EP0002, conversation.py). No separate story needed.

---

## Open Questions

None.

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-04-05 | Claude | Initial epic generation from PRD |
