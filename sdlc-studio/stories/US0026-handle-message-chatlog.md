# US0026: Implement `_async_handle_message` + adopt `ChatLog`

> **Status:** Proposed
> **Epic:** [EP0007: Bridge v4.36 + Modern HA Re-Alignment](../epics/EP0007-bridge-v436-modern-ha-realignment.md)
> **Owner:** Darren Benson
> **Created:** 2026-06-01

## User Story

**As a** Home Assistant operator
**I want** the conversation entity to use HA's `ChatLog` for history and LLM-API plumbing
**So that** conversation history is first-class and the bespoke `SessionManager` history is retired

## User Story Context

G3: HA promoted `_async_handle_message(user_input, chat_log)` specifically to hand the entity a `ChatLog` for history + LLM-API plumbing. The component still overrides `async_process(user_input)` and reinvents history via the ad-hoc `SessionManager`, so it cannot call `chat_log.async_provide_llm_data()` to wire the Assist LLM API and reinvents the tool-call loop `ChatLog` manages natively.

## Acceptance Criteria

### AC1: Implement `_async_handle_message` with `ChatLog`
- **Given** a conversation turn
- **When** the entity handles it
- **Then** it implements `_async_handle_message(self, user_input, chat_log)`, adds user content via `chat_log.async_add_user_content` and appends assistant/tool content via `ChatLog` methods, returning a `ConversationResult`
- **Verify:** `pytest` invoking `_async_handle_message` with a fake `ChatLog` asserts user + assistant content are appended to the log and a `ConversationResult` is returned

### AC2: History sourced from `ChatLog`
- **Given** history
- **When** a multi-turn conversation occurs
- **Then** it is read from `ChatLog` (the `SessionManager` is no longer the history source)
- **Verify:** `pytest` asserting multi-turn history is read from the `ChatLog`, not `SessionManager`

## Scope

### In Scope
- `_async_handle_message(self, user_input, chat_log)` entry point
- User/assistant/tool content via `ChatLog` methods
- Retire `SessionManager` as the history source

### Out of Scope
- LLM-API actuation wiring via `async_provide_llm_data()` (US0027)
- Discovery/health surface (US0028)

## Technical Notes

- `_async_handle_message` is the promoted entry point that hands the entity a `ChatLog`; do not keep overriding `async_process`.
- `ChatLog` manages the tool-call loop natively — do not reinvent it.

## Dependencies

### Story Dependencies

| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| US0025 | Platform | `ConversationEntity` per agent to host `_async_handle_message` | Proposed |

## Estimation

**Story Points:** 5
**Complexity:** High

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-06-01 | Claude | Initial story for EP0007 (CR-0002 redesign) |
