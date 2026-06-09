# Bug Registry

**Last Updated:** 2026-06-09

## Summary

| Status | Count |
|--------|-------|
| Open | 0 |
| Fixed | 10 |
| In Progress | 0 |
| Closed | 0 |
| **Total** | **10** |

## Bugs

| ID | Title | Severity | Priority | Status | Component |
|----|-------|----------|----------|--------|-----------|
| [BG0001](BG0001-no-voice-agent-selection-in-options.md) | No way to change voice agent after setup | High | P1 | Fixed | config_flow.py |
| [BG0002](BG0002-config-flow-asks-for-two-agents.md) | Config flow asks for two agents unnecessarily | Medium | P2 | Fixed | config_flow.py |
| [BG0003](BG0003-picker-lists-models-and-non-agents.md) | Agent picker lists models/chatbots/workerbots | Medium | P2 | Fixed | config_flow.py |
| [BG0004](BG0004-caller-id-not-registered-auth-error.md) | Conversation fails with "authentication problem" — default caller_id `homeassistant` rejected by bridge v4.36 | High | P1 | Fixed | const/client/config_flow/conversation |
| [BG0005](BG0005-conversation-entity-shows-raw-agent-id.md) | Conversation entity shows the raw bridge agent id instead of the agent name | Medium | P2 | Fixed | conversation.py |
| [BG0006](BG0006-token-sensor-crashes-on-null-totals.md) | Usage token sensor raises on null/non-numeric totals; 0-vs-None; dead translation_key | High | P2 | Fixed | sensor.py |
| [BG0007](BG0007-fleet-doctor-issue-lifecycle.md) | Fleet-doctor repair issue wrongly cleared on bridge outage + churns every poll | Medium | P2 | Fixed | coordinator/drift |
| [BG0008](BG0008-coordinator-emits-observability-by-reference.md) | Coordinator emits usage/doctor by reference (aliasing hazard) | Low | P3 | Fixed | coordinator/sensor |
| [BG0009](BG0009-first-run-picker-lost-status-label.md) | First-run agent picker lost its health/crew label (BG0005 regression) | Low | P3 | Fixed | config_flow.py |
| [BG0010](BG0010-brand-icon-wrong-location.md) | Brand icon in wrong location — "icon not available" (needs `brand/` subdir, HA 2026.3+) | Low | P3 | Fixed | brand assets |

## Notes

- BG0006..BG0009 came from the RV0006 xhigh code review of the 0.10.0 release (2026-06-09). All four are in the CR-0009/BG0005 code shipped this release; fixed together and shipped as 0.10.1.

- BG0001 and BG0002 were both resolved by the EP0007 realignment (single-agent setup + options agent picker + per-agent subentries) and closed as Fixed in the Wave 5 backlog reconcile (2026-06-09); the records had simply never been closed. Live UI confirmation lands on the next deploy.
- BG0001 and BG0002 are related -- fixing both together would simplify the config flow to a single agent selector in setup, with an optional voice agent override in the options flow
- Both found during first live deployment on HA 2026.4.1
- BG0004 found on the live deployment (HA 2026.5.4, bridge v4.36): the bridge now requires `x-bridge-mcp-caller` to be a registered agent id, so the `homeassistant` default broke every conversation turn. Fixed in-repo; live-deploy + Assist E2E still pending. Cross-repo follow-up: provision a dedicated `homeassistant` caller + crew on the bridge (US0031) — also un-orphans `conversation.dbee_dbee`.
- BG0005 found on the live deployment (2026-06-09) while reviewing the Assist screen: the conversation entity for `default_agent` installs (no subentry) is named with the raw bridge id (`Cora openclaw-openclaw-cora`) instead of `name (crew)`. Root cause confirmed from `/api/states`; the legacy fallback in `_agents_from_entry` echoes the id as the display name. Naming-consistency theme overlaps [CR-0007](../change-requests/cr0007.md).
