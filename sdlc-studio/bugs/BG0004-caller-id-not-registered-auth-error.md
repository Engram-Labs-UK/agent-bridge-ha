# BG0004: Conversation fails with "authentication problem" — default caller_id `homeassistant` rejected by bridge v4.36 crew check

> **Status:** Fixed
> **Severity:** High
> **Priority:** P1
> **Reporter:** Darren
> **Assignee:** Claude
> **Created:** 2026-06-03

## Summary

Every conversation turn to every agent fails. Speaking to Cora returns *"There is
an authentication problem with the bridge."* The bridge token is valid and the
health sensors show `ok`/`connected`, so the message misdirects toward a credentials
problem when the real cause is the **caller identity header**.

The integration sends `x-bridge-mcp-caller: homeassistant` (the `DEFAULT_CALLER_ID`)
on every request. Bridge v4.36 requires that header to be a **registered agent id** so
it can resolve the caller's crew for cross-agent dispatch. `homeassistant` is not a
registered agent, so the bridge denies chat with HTTP 403 (`TOOL_PERMISSION_DENIED`,
*"Caller 'homeassistant' is not a registered agent"*). `client._request` converts any
401/403 into `BridgeAuthError(code="AUTH_ERROR")`, which `conversation.py` maps to the
generic token-failure string.

## Affected Area

- **Epic:** [EP0007: Bridge v4.36 + Modern HA Re-Alignment](../epics/EP0007-bridge-v436-modern-ha-realignment.md)
- **Story:** [US0028: v4.36 discovery/health surface (caller header, G9)](../stories/US0028-v436-discovery-health-surface.md)
- **Component:** const.py (`DEFAULT_CALLER_ID`), __init__.py / config_flow.py (caller wiring), client.py (error classification), conversation.py (error message)

## Environment

- **Version:** 0.3.1 (deployed on HA 2026.5.4, bridge v4.36 at `http://10.0.0.210:18780`)
- **Platform:** Home Assistant custom component

---

## Reproduction Steps

1. Configure the integration against a bridge running v4.36 (default `caller_id`, i.e. `homeassistant`).
2. Open Assist (or a voice satellite) and speak to any agent, e.g. Cora.
3. Observe the reply: "There is an authentication problem with the bridge."

Reproduced at the bridge directly:

```
# 403 with the integration's caller header:
curl -X POST -H "Authorization: Bearer <token>" -H "x-bridge-mcp-caller: homeassistant" \
  http://10.0.0.210:18780/v1/chat/completions -d '{"agent":"openclaw-openclaw-cora","messages":[{"role":"user","content":"ping"}]}'
# -> HTTP 403  {"error":{"code":"TOOL_PERMISSION_DENIED","message":"Caller 'homeassistant' is not a registered agent ..."}}

# 200 with a registered agent id as caller:
curl ... -H "x-bridge-mcp-caller: openclaw-openclaw-cora" ... -> HTTP 200 ("Pong.")
curl ... -H "x-bridge-mcp-caller: dbee" ...                 -> HTTP 200
# 200 with no caller header at all                          -> HTTP 200
```

## Expected Behaviour

Out of the box against a v4.36 bridge, conversation turns succeed. If the caller
identity genuinely cannot be authorised, the user sees an actionable message that
points at the caller configuration, not a generic token/auth failure.

## Actual Behaviour

All conversation turns fail with HTTP 403 from the bridge, surfaced to the user as
"There is an authentication problem with the bridge." The token is valid; health
sensors stay green because both `/health` calls use `auth=False` and never exercise
the caller check.

---

## Root Cause Analysis

`DEFAULT_CALLER_ID = "homeassistant"` (`const.py:40`) is an aspirational identity
from the US0028/G9 design that assumed a `homeassistant` caller would be **registered
on the bridge** (the fleet-provisioning side, tracked in US0031). That provisioning
never happened, and bridge v4.36 now enforces caller-is-a-registered-agent for
cross-agent dispatch. The header is sent on every request (`client.py:60-64`), so the
denial hits both discovery (tolerated, 200) and chat (403).

Two compounding faults:

1. **Wrong effective default.** `homeassistant` is not a registered agent; the
   configured `default_agent` always is. The integration never falls back to it.
2. **Mislabelled error.** `client._request` (`client.py:92`) and the streaming path
   (`client.py:240`) raise `BridgeAuthError("AUTH_ERROR")` for *any* 401/403 without
   inspecting the body, so a caller-permission denial (`TOOL_PERMISSION_DENIED`) is
   reported as a token-authentication failure.

`caller_id` is also not editable in the options flow (`config_flow.py` reads it but
never offers it), so an operator cannot correct it from the UI.

Related: `conversation.dbee_dbee` is orphaned/`unavailable` because DBee is
`team: system` and the CR-0003 crew filter excludes it — a separate concern, partly
operator-gated (US0031 fleet provisioning of a dedicated `homeassistant` caller +
crew). This bug covers only the auth-error breakage.

## Fix Description

Three coordinated changes:

1. **Sensible effective caller (the unblock).** New `helpers.resolve_caller_id(entry)`
   returns the explicit `caller_id` option if set, else the configured `default_agent`
   (always a registered agent), else `DEFAULT_CALLER_ID`. Wired into `__init__.py` and
   `config_flow._discover_agents`. The integration now sends a registered agent id as
   the caller out of the box, so chat works without bridge-side provisioning.
2. **Operator override.** `caller_id` is now an editable field in the options flow
   (`async_step_init`), with strings/translations, so a dedicated HA caller can be
   pointed at once the fleet provisions one (US0031). Blank = use the selected agent.
3. **Honest error.** New `BridgeCallerError(code="CALLER_ERROR")` distinguishes a
   caller-identity denial from a token failure. `client._request`/`chat_stream` now
   read the 403 body and raise `BridgeCallerError` when the bridge returns
   `TOOL_PERMISSION_DENIED`/a caller-related message, else `BridgeAuthError`. 401 is
   always a token error. `conversation.py` maps `CALLER_ERROR` to an actionable message
   pointing at the caller ID option.

Verified against the live bridge (`http://10.0.0.210:18780`): caller `homeassistant`
→ chat 403; caller `openclaw-openclaw-cora` (the live `default_agent`, hence the new
resolved value) → 200. The fix resolves the reproduced failure.

### Files Modified

| File | Change |
|------|--------|
| custom_components/agent_bridge/client.py | Added `BridgeCallerError`, `_is_caller_permission_error`, `_error_payload`; 403 now classified (caller vs token) in `_request` and streaming path; 401 stays token-auth |
| custom_components/agent_bridge/helpers.py | Added `resolve_caller_id(entry)` (explicit option → default_agent → DEFAULT_CALLER_ID) |
| custom_components/agent_bridge/__init__.py | Use `resolve_caller_id(entry)` instead of raw `homeassistant` default |
| custom_components/agent_bridge/config_flow.py | Use `resolve_caller_id` in `_discover_agents`; add editable `caller_id` field to options `async_step_init` |
| custom_components/agent_bridge/conversation.py | Add `CALLER_ERROR` voice-friendly message |
| custom_components/agent_bridge/strings.json, translations/en.json | Label + description for the `caller_id` options field |

### Tests Added

| Test | Description | File |
|------|-------------|------|
| `test_403_tool_permission_denied_raises_caller_error` | 403 + `TOOL_PERMISSION_DENIED` → `BridgeCallerError` | tests/test_client.py |
| `test_403_caller_message_without_known_code_raises_caller_error` | message-based classification for unknown codes | tests/test_client.py |
| `test_403_without_caller_signal_raises_auth_error` | bare 403 stays `BridgeAuthError` | tests/test_client.py |
| `test_401_is_never_a_caller_error` | 401 always token-auth | tests/test_client.py |
| `test_bridge_caller_error` | exception code/hierarchy | tests/test_client.py |
| `TestResolveCallerId` (4 cases) | precedence: explicit → default_agent → default; blank falls back | tests/test_helpers.py |

---

## Verification

- [x] Fix verified in development (logic verified against live bridge; runnable unit tests pass — `tests/test_client.py`, `tests/test_helpers.py`: 58 passed)
- [ ] Regression tests pass — full suite needs Python 3.13 + HA 2026.2.3 (CI only; local toolchain is Python 3.12). New unit tests pass on the runnable subset.
- [ ] No side effects observed — pending live deploy + an Assist turn against Cora

**Verified by:** Claude (partial — CI + live E2E pending)
**Verification date:** 2026-06-03

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-06-03 | Claude | Bug reported (root cause confirmed against live bridge) |
| 2026-06-03 | Claude | Status → In Progress |
| 2026-06-03 | Claude | Status → Fixed: caller resolution + options field + caller/token error split; 11 regression tests added |
