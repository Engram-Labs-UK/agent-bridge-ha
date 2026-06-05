# US0032: Session continuity via idle-windowed channel key

> **Status:** Done
> **Epic:** [EP0008: Conversation Capability Expansion](../epics/EP0008-conversation-capability-expansion.md)
> **Owner:** Darren Benson
> **Created:** 2026-06-05

## User Story

**As a** Home Assistant user talking to a bridge agent
**I want** consecutive commands within a short window to share conversational context
**So that** multi-turn tasks ("turn off the lights" → "actually just the kitchen") work instead
of cold-starting every turn

## User Story Context

Phase 0 spike (CR-0004) proved the bridge already persists a session per `channel` with a 24h
TTL (`MessageRouter.getSessionId/setSessionId`). HA sends `channel=conversation_id`, which is
ephemeral (a fresh id per non-continuation command), so the bridge session is abandoned between
commands. The fix is the channel **key**, not a session store: send a channel that stays stable
across an idle window, then rotates so context doesn't accumulate for 24h. HA cannot set a
per-request TTL (the bridge uses its server `sessionTtlMs`), so HA rotates the key.

## Acceptance Criteria

### AC1: Stable channel key per scope
- **Given** a conversation turn with a resolvable scope (device/area/user)
- **When** the entity builds the outbound request
- **Then** `channel` = `ha:{agent_id}:{scope}:{epoch}`, where `scope` falls back
  `dev:{device_id}` → `usr:{user_id}` → `default` (area is derived from the device, so a device
  id already covers it), and `epoch` is the current rotation token for that scope
- **Verify:** `pytest` asserts the channel format and the scope fallback order

### AC2: Idle-window rotation
- **Given** a prior turn for a scope at time T
- **When** a new turn arrives at T+Δ
- **Then** if Δ ≤ `idle_window` the same `epoch` (and channel) is reused; if Δ > `idle_window` a
  new `epoch` is minted (fresh session). Last-activity is updated each turn.
- **Verify:** `pytest` with a controllable clock asserts reuse within the window and rotation after

### AC3: Configurable idle window
- **Given** the integration options
- **When** the operator sets the session idle window
- **Then** it is honoured (default 600 s)
- **Verify:** `pytest` asserts default and override are applied

### AC4: No regression to caller_context / grounding
- **Given** the 0.4.0 caller_context + source block
- **When** the channel key changes
- **Then** caller_context, system prompt and audit events are unchanged
- **Verify:** existing conversation tests stay green

## Scope

### In Scope
- Channel-key builder + per-scope idle map in `hass.data`
- `CONF_SESSION_IDLE_WINDOW` option (default 600 s)
- Optional: capture/log returned `session_id` for observability

### Out of Scope
- Building any HA-side session content store (the bridge owns session state)
- Streaming (US0033), confirm flow (US0036)

## Technical Notes

- Touchpoints: `conversation.py` (`_async_handle_message` channel construction + idle map),
  `const.py` (option + default). `client.py` unchanged (still passes `channel`).
- Epoch can be a monotonically increasing counter or a coarse time token per scope; rotation is
  driven by `now - last_activity > idle_window`.
- Use HA time (`dt_util.utcnow()`); store `{scope: (epoch, last_activity)}` in `hass.data[DOMAIN]`.

## Dependencies

| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| Phase 0 spike | Finding | Bridge persists session by channel (24h TTL) | Done |

## Estimation

**Story Points:** 3
**Complexity:** Medium

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-06-05 | Claude | Initial story for EP0008 (CR-0004), Phase 1 |
| 2026-06-05 | Claude | Implemented (`_session_scope`/`_session_channel` + per-entity epoch map + `CONF_SESSION_IDLE_WINDOW` in options flow). Full review applied: UTC clock + rotate-on-rewind, stale-scope pruning (bridge TTL), config-flow exposure. Unit-tested (logic verified locally; full pytest CI-gated). Status → Done |
