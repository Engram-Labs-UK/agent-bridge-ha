# US0039: AI Task platform (generate_data, scoped)

> **Status:** Done
> **Epic:** [EP0008: Conversation Capability Expansion](../epics/EP0008-conversation-capability-expansion.md)
> **Owner:** Darren Benson
> **Created:** 2026-06-05

## User Story

**As an** automation/dashboard author
**I want** to ask a bridge agent for structured data or a summary
**So that** I can use AI output in templates, automations and dashboards

## User Story Context

HA's `ai_task` platform exposes `AITaskEntity._async_generate_data(task, chat_log)` returning
`GenDataTaskResult`, honouring `task.structure` (→ JSON) and `task.attachments`. Cora flagged
this as a potential tarpit — keep it tightly scoped (no schema registry, no approval workflow).

## Acceptance Criteria

### AC1: AI Task entity per agent
- **Given** the integration with agents
- **When** the platform loads
- **Then** one `ai_task` entity per agent is created
- **Verify:** `pytest` asserts entities created per agent

### AC2: generate_data with structure
- **Given** `ai_task.generate_data` with a `structure`
- **When** invoked
- **Then** the entity returns `GenDataTaskResult` with data conforming to the structure (JSON)
- **Verify:** `pytest` asserts structured JSON returned for a sample schema

### AC3: Free-text generate_data
- **Given** no structure
- **When** invoked
- **Then** the entity returns text
- **Verify:** `pytest` asserts text result when structure is absent

## Scope

### In Scope
- New `ai_task.py` platform; `"ai_task"` in `PLATFORMS`; reuse `client.chat()`; share chat-log
  processing with the conversation entity
### Out of Scope
- `generate_image` (only if a model supports it); schema registry; approval workflows

## Technical Notes

- Touchpoints: new `ai_task.py`, `const.py PLATFORMS`. Parse/validate structure → JSON.

## Estimation

**Story Points:** 5
**Complexity:** Medium

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-06-05 | Claude | Initial story for EP0008 (CR-0004), Phase 6 |
| 2026-06-05 | Claude | Implemented `ai_task.py` (one AITaskEntity per agent; `generate_data` → text, or JSON when a `structure` is requested, with code-fence stripping; BridgeError/parse errors → HomeAssistantError); `"ai_task"` added to PLATFORMS. Scoped per Cora: no image gen / schema registry / approval workflow. `_strip_code_fence` verified locally; entity tests CI-gated (ai_task component). Self-review: additive new platform, existing paths untouched; reuses conversation helpers. Status → Done |
