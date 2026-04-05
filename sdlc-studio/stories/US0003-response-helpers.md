# US0003: Response Helpers

> **Status:** Done
> **Epic:** [EP0001: Bridge Foundation](../epics/EP0001-bridge-foundation.md)
> **Owner:** Darren Benson
> **Created:** 2026-04-05

## User Story

**As the** integration
**I want** reliable text extraction from varying bridge response structures
**So that** the conversation agent always gets usable response text regardless of response format

## Context

Different bridge agents return responses in different structures. Some nest content deeply. The helper must traverse responses using priority keys (text, content, message, output_text) up to 8 levels deep.

---

## Acceptance Criteria

### AC1: Priority key extraction
- **Given** a response dict with a top-level "content" key
- **When** extract_response_text() is called
- **Then** it returns the value of "content"

### AC2: Nested extraction
- **Given** a response nested 5 levels deep with "text" at the deepest level
- **When** extract_response_text() is called
- **Then** it traverses recursively and returns the text value

### AC3: Depth limit
- **Given** a response nested 9 levels deep
- **When** extract_response_text() is called
- **Then** it stops at 8 levels and returns None

### AC4: Priority ordering
- **Given** a response with both "text" and "content" at the same level
- **When** extract_response_text() is called
- **Then** it returns "text" (first in priority order)

### AC5: Tool calls extraction
- **Given** a chat completion response with tool_calls in choices[0].message
- **When** extract_tool_calls() is called
- **Then** it returns the list of tool_call objects

---

## Scope

### In Scope
- `custom_components/agent_bridge/helpers.py`
- extract_response_text(data: dict) -> str | None
- extract_tool_calls(data: dict) -> list[dict]
- Text normalisation (strip whitespace, None handling)

### Out of Scope
- Bridge client HTTP logic (US0002)
- Tool call execution (EP0002)

---

## Technical Notes

Priority keys from const.py: TEXT_PRIORITY_KEYS = ("text", "content", "message", "output_text"). Recursive traversal: for each level, check priority keys first, then recurse into dict values. Also handle the OpenAI chat completion format: choices[0].message.content as a special fast path.

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| Response is None | Return None |
| Response is empty dict | Return None |
| Response has list values | Recurse into first dict element in list |
| Response text is empty string | Return empty string (valid) |
| Response has non-string text value (int, bool) | Convert to string |
| Circular reference (shouldn't happen with JSON) | Depth limit prevents infinite recursion |

---

## Test Scenarios

- [ ] Top-level "text" key extracted
- [ ] Top-level "content" key extracted
- [ ] Top-level "message" key extracted
- [ ] Top-level "output_text" key extracted
- [ ] Nested 3 levels deep: response.choices[0].message.content
- [ ] Nested 5 levels deep extraction works
- [ ] Nested 9 levels deep returns None (depth limit)
- [ ] Priority: "text" chosen over "content" at same level
- [ ] Empty dict returns None
- [ ] None input returns None
- [ ] String value returned as-is
- [ ] Integer value converted to string
- [ ] extract_tool_calls returns tool_calls array from chat completion
- [ ] extract_tool_calls returns empty list when no tool_calls

---

## Dependencies

### Story Dependencies

| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| [US0001](US0001-project-scaffold.md) | Hard | const.py for TEXT_PRIORITY_KEYS, MAX_TEXT_DEPTH | Done |

---

## Estimation

**Story Points:** 2
**Complexity:** Low

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-04-05 | Claude | Initial story generation |
