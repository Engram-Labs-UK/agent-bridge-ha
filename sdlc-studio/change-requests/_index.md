# Change Request Registry

**Last Updated:** 2026-06-03
**PRD Reference:** [Product Requirements Document](../prd.md)

## Summary

| Status | Count |
| --- | --- |
| Proposed | 1 |
| Review | 1 |
| Implemented | 1 |
| Rejected | 0 |
| Deferred | 0 |
| **Total** | **3** |

## By Priority

| Priority | Proposed | Review | Implemented |
| --- | --- | --- | --- |
| P1 | 1 | 1 | 0 |
| P2 | 0 | 0 | 1 |
| P3 | 0 | 0 | 0 |
| P4 | 0 | 0 | 0 |

## All Change Requests

| ID | Title | Priority | Status | Type | Linked Epics | Date |
| --- | --- | --- | --- | --- | --- | --- |
| [CR-0001](cr0001.md) | Multiple config entries for per-agent voice pipelines | P1 | Proposed | design-change | — (superseded by CR-0002) | 2026-04-06 |
| [CR-0002](cr0002.md) | Re-align to Bridge v4.36 + modern HA conversation APIs | P1 | Review | design-change | [EP0007](../epics/EP0007-bridge-v436-modern-ha-realignment.md) | 2026-06-01 |
| [CR-0003](cr0003.md) | Crew-scoped agent picker + editable per-agent instructions + HA-origin prompt | P2 | Implemented | production-feedback | [EP0007](../epics/EP0007-bridge-v436-modern-ha-realignment.md) | 2026-06-02 |

## Dependencies

| CR | Depends On | Dependency Status |
| --- | --- | --- |
| CR-0001 | BG0001, BG0002 | Open, Open |
| CR-0002 | EP0002, EP0004 | Done, Done |
| CR-0003 | — | — |

## Notes

- CRs are numbered globally (CR-0001, CR-0002, etc.)
- Priority: P1 (critical gap) > P2 (important) > P3 (desirable) > P4 (nice to have)
- Types: feature-request, production-feedback, spec-gap, retrospective, design-change
- **CR-0002 supersedes CR-0001** — the one-entry-per-agent workaround was replaced by `ConversationEntity` + config subentries. CR-0001 stays `Proposed` (never actioned) for the historical record.
- CR-0002 and CR-0003 are both realised through **EP0007**. CR-0002 stays `Review` while US0021/US0027/US0031 are operator-gated; CR-0003 is `Implemented` (261 tests green) and addressed [BG0003](../bugs/BG0003-picker-lists-models-and-non-agents.md).
- Status values in use: `Proposed` | `Review` | `Implemented` | `Rejected` | `Deferred`. Use `/sdlc-studio cr close --cr CR-NNNN` to move a CR to a terminal state.
