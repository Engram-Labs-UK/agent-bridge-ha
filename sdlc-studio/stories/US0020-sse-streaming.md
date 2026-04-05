# US0020: SSE Streaming

> **Status:** Done
> **Epic:** [EP0006: Advanced Voice](../epics/EP0006-advanced-voice.md)
> **Owner:** Darren Benson
> **Created:** 2026-04-05

## User Story

**As a** voice satellite user
**I want** agent responses to stream
**So that** I hear the first words sooner rather than waiting for the complete response

## Acceptance Criteria

### AC1: Client Streaming Method
- **Given** the bridge client
- **When** `chat_stream()` is called with messages, agent, and channel
- **Then** it sends `POST /v1/chat/completions` with `stream: true` and returns an async iterator of content delta strings

### AC2: SSE Chunk Parsing
- **Given** the bridge returns SSE chunks in OpenAI format
- **When** each `data:` line arrives
- **Then** the delta content is extracted from `choices[0].delta.content` and yielded

### AC3: Stream Termination
- **Given** the bridge sends `data: [DONE]`
- **When** the iterator encounters it
- **Then** iteration stops cleanly

### AC4: Conversation Agent Streaming Assembly
- **Given** a voice request
- **When** the conversation agent processes it
- **Then** it attempts streaming first, assembles deltas into a complete response string, and returns a ConversationResult

### AC5: Fallback to Non-Streaming
- **Given** streaming fails (SSE parse error, timeout, bridge doesn't support it)
- **When** the error occurs
- **Then** the conversation agent retries with non-streaming `chat()` and returns that result

### AC6: Streaming Timeout
- **Given** streaming is in progress
- **When** no data arrives for 300 seconds (configurable via DEFAULT_STREAMING_TIMEOUT)
- **Then** the stream is abandoned and fallback to non-streaming occurs

## Scope

### In Scope
- `chat_stream()` async generator method in BridgeClient
- SSE line parsing (data: prefix, [DONE] sentinel)
- Streaming assembly in conversation agent `async_process()`
- Fallback path on streaming failure
- Tool call extraction from streamed responses (accumulated message)

### Out of Scope
- Streaming for text (non-voice) requests
- Partial TTS playback (HA pipeline handles that)
- Streaming for per-agent conversation agents (Phase 3)

## Technical Notes

- SSE format per TRD: `data: {"id": "chatcmpl-xxx", "choices": [{"delta": {"content": "word"}}]}`
- Final chunk: `data: [DONE]`
- Tool calls in streaming: accumulate `tool_calls` deltas across chunks, process after stream ends
- Use `aiohttp` response content iteration with `resp.content.iter_any()` or line-based reading
- Streaming timeout uses `asyncio.timeout()` (Python 3.11+) or `async_timeout`

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| Bridge returns non-SSE response to stream request | Fallback to non-streaming |
| SSE chunk has no delta.content | Skip chunk, continue |
| Connection drops mid-stream | Fallback to non-streaming retry |
| Stream returns tool_calls | Accumulate, process after [DONE], enter tool loop |
| Empty stream (only [DONE]) | Return empty response text |

## Dependencies

### Story Dependencies

| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| US0002 | Service | BridgeClient._request pattern | Done |
| US0007 | Service | Conversation agent async_process | Done |

## Estimation

**Story Points:** 5
**Complexity:** High

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-04-05 | Claude | Initial story for Phase 2 implementation |
