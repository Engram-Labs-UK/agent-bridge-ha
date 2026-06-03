# Bug Registry

**Last Updated:** 2026-06-03

## Summary

| Status | Count |
|--------|-------|
| Open | 2 |
| Fixed | 2 |
| In Progress | 0 |
| Closed | 0 |
| **Total** | **4** |

## Bugs

| ID | Title | Severity | Priority | Status | Component |
|----|-------|----------|----------|--------|-----------|
| [BG0001](BG0001-no-voice-agent-selection-in-options.md) | No way to change voice agent after setup | High | P1 | Open | config_flow.py |
| [BG0002](BG0002-config-flow-asks-for-two-agents.md) | Config flow asks for two agents unnecessarily | Medium | P2 | Open | config_flow.py |
| [BG0003](BG0003-picker-lists-models-and-non-agents.md) | Agent picker lists models/chatbots/workerbots | Medium | P2 | Fixed | config_flow.py |
| [BG0004](BG0004-caller-id-not-registered-auth-error.md) | Conversation fails with "authentication problem" — default caller_id `homeassistant` rejected by bridge v4.36 | High | P1 | Fixed | const/client/config_flow/conversation |

## Notes

- BG0001 and BG0002 are related -- fixing both together would simplify the config flow to a single agent selector in setup, with an optional voice agent override in the options flow
- Both found during first live deployment on HA 2026.4.1
- BG0004 found on the live deployment (HA 2026.5.4, bridge v4.36): the bridge now requires `x-bridge-mcp-caller` to be a registered agent id, so the `homeassistant` default broke every conversation turn. Fixed in-repo; live-deploy + Assist E2E still pending. Cross-repo follow-up: provision a dedicated `homeassistant` caller + crew on the bridge (US0031) — also un-orphans `conversation.dbee_dbee`.
