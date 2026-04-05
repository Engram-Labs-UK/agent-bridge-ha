# US0010: Continuation Detection

> **Status:** Done
> **Epic:** [EP0002: Conversation & Home Control](../epics/EP0002-conversation-and-control.md)
> **Owner:** Darren Benson
> **Created:** 2026-04-05

## User Story

**As a** voice satellite user
**I want** the agent to keep listening when it asks me a follow-up question
**So that** I can respond naturally without needing to re-trigger the wake word

## Context

Agents often end responses with follow-up questions: "Would you like me to turn off the rest of the lights too?" Without continuation detection, the voice pipeline closes and the user must say the wake word again. This story analyses the final sentence of agent responses for question patterns and sets `continue_conversation: True` in ConversationResult when appropriate. Exclusion phrases prevent false positives from rhetorical questions. Both continuation phrases and exclusion phrases are configurable. Lives in `conversation.py` as an internal function.

---

## Acceptance Criteria

### AC1: Question pattern detection
- **Given** an agent response where the final sentence ends with "?"
- **When** the response is analysed
- **Then** continuation is triggered only if the final sentence also contains a continuation phrase

### AC2: Default continuation phrases
- **Given** no custom configuration
- **When** continuation detection runs
- **Then** the default phrases are: "would you like", "shall I", "do you want", "should I", "which one", "what would you prefer"

### AC3: Default exclusion phrases
- **Given** no custom configuration
- **When** a final sentence ends with "?" but matches an exclusion phrase
- **Then** continuation is not triggered
- **And** the default exclusions are: "right?", "isn't it?", "okay?", "yeah?", "let me know if you need anything"

### AC4: ConversationResult flag
- **Given** continuation is detected
- **When** the ConversationResult is constructed
- **Then** `continue_conversation` is set to True

### AC5: No continuation by default
- **Given** an agent response that does not match continuation patterns
- **When** the ConversationResult is constructed
- **Then** `continue_conversation` is False (or not set)

### AC6: Configurable continuation phrases
- **Given** custom continuation phrases in config/options
- **When** continuation detection runs
- **Then** the custom phrases are used instead of (or in addition to) defaults

### AC7: Configurable exclusion phrases
- **Given** custom exclusion phrases in config/options
- **When** continuation detection runs
- **Then** the custom exclusions are used instead of (or in addition to) defaults

### AC8: Case-insensitive matching
- **Given** an agent response with mixed case ("Would You Like me to...")
- **When** continuation detection runs
- **Then** matching is case-insensitive

---

## Scope

### In Scope
- Continuation detection function in `custom_components/agent_bridge/conversation.py`
- Final sentence extraction from agent response text
- Pattern matching against continuation and exclusion phrase lists
- Setting continue_conversation on ConversationResult
- Default phrase lists as constants (in const.py or inline)
- Configuration support for custom phrase lists

### Out of Scope
- Voice pipeline wake word behaviour (HA controls this based on continue_conversation)
- NLP/ML-based intent detection (simple string matching is sufficient)
- Streaming response continuation (EP0006)

---

## Technical Notes

Extract the final sentence by splitting on sentence-ending punctuation (`. `, `! `, `? `, or end of string) and taking the last non-empty segment. Check if it ends with `?`. If yes, check for exclusion match first (if any exclusion phrase appears in the final sentence, do not continue). Then check if any continuation phrase appears in the final sentence. All matching is case-insensitive. The function signature should be something like `should_continue(text: str, continuation_phrases: list[str], exclusion_phrases: list[str]) -> bool`.

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| Empty response text | No continuation (return False) |
| Response is a single question with no continuation phrase | No continuation ("What time is it?") |
| Response ends with continuation question after multiple sentences | Continuation detected (only final sentence matters) |
| Exclusion phrase in non-final sentence, continuation in final | Continuation triggered (exclusion only checked against final sentence) |
| Response ends with "right?" | Excluded, no continuation |
| Response ends with "Would you like me to do that, right?" | Exclusion match takes priority, no continuation |
| Multiple question marks: "Really??" | Still detected as question ending |
| Response with no punctuation ending in continuation phrase | No continuation (must end with ?) |
| Unicode question mark (e.g. fullwidth ？) | Not matched (ASCII ? only, sufficient for English) |

---

## Test Scenarios

- [ ] "Would you like me to turn off the lights?" -- continuation True
- [ ] "Shall I set the temperature to 20?" -- continuation True
- [ ] "Do you want me to lock the doors?" -- continuation True
- [ ] "Should I close the blinds too?" -- continuation True
- [ ] "Which one would you prefer?" -- continuation True
- [ ] "What would you prefer?" -- continuation True
- [ ] "Done. The lights are off." -- continuation False (no question)
- [ ] "What time is it?" -- continuation False (no continuation phrase)
- [ ] "I've turned them on, right?" -- continuation False (exclusion match)
- [ ] "All done, isn't it?" -- continuation False (exclusion match)
- [ ] "Let me know if you need anything?" -- continuation False (exclusion match)
- [ ] "I've set the lights. Would you like me to adjust the thermostat?" -- continuation True (final sentence)
- [ ] "" (empty string) -- continuation False
- [ ] "WOULD YOU LIKE ME TO DO THAT?" -- continuation True (case-insensitive)
- [ ] Custom phrases: "want me to" added -- "Want me to close it?" triggers continuation
- [ ] Custom exclusions: "got it?" added -- "Got it?" does not trigger continuation
- [ ] Exclusion takes priority over continuation in same sentence

---

## Dependencies

### Story Dependencies

| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| [US0007](US0007-conversation-agent-core.md) | Hard | Conversation agent processes responses, constructs ConversationResult | Done |

### External Dependencies

| Dependency | Type | Status |
|------------|------|--------|
| Home Assistant Core 2025.1.0+ | Framework | Available |
| ConversationResult.continue_conversation | HA API | Available (2025.1.0+) |

---

## Estimation

**Story Points:** 2
**Complexity:** Low

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-04-05 | Claude | Initial story generation |
