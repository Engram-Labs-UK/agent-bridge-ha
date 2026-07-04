# Change Request Registry

**Last Updated:** 2026-07-04
**PRD Reference:** [Product Requirements Document](../prd.md)

## Summary

| Status | Count |
| --- | --- |
| Proposed | 1 |
| Review | 2 |
| Implemented | 12 |
| Rejected | 0 |
| Deferred | 1 |
| **Total** | **16** |

## By Priority

| Priority | Proposed | Review | Implemented | Deferred |
| --- | --- | --- | --- | --- |
| P1 | 0 | 1 | 1 | 1 |
| P2 | 0 | 1 | 7 | 0 |
| P3 | 1 | 0 | 4 | 0 |
| P4 | 0 | 0 | 0 | 0 |

> The two remaining **Review** CRs (CR-0002, CR-0004) are **component-complete**: all
> in-repo code is shipped and CI-green; their only outstanding ACs are operator-gated
> (live E2E / human TTS perception) or cross-repo (bridge PR #42, agent harness
> provisioning), tracked in `IMPLEMENTATION-KICKOFF.md`. They are not marked Implemented
> because that would falsely imply those external ACs are verified.

## All Change Requests

| ID | Title | Priority | Status | Type | Linked Epics | Date |
| --- | --- | --- | --- | --- | --- | --- |
| [CR-0001](cr0001.md) | Multiple config entries for per-agent voice pipelines | P1 | Deferred | design-change | — (superseded by CR-0002) | 2026-04-06 |
| [CR-0002](cr0002.md) | Re-align to Bridge v4.36 + modern HA conversation APIs | P1 | Review | design-change | [EP0007](../epics/EP0007-bridge-v436-modern-ha-realignment.md) | 2026-06-01 |
| [CR-0003](cr0003.md) | Crew-scoped agent picker + editable per-agent instructions + HA-origin prompt | P2 | Implemented | production-feedback | [EP0007](../epics/EP0007-bridge-v436-modern-ha-realignment.md) | 2026-06-02 |
| [CR-0004](cr0004.md) | Reactive continuity + proactive + multimodal conversation expansion | P2 | Review | feature-request | [EP0008](../epics/EP0008-conversation-capability-expansion.md) | 2026-06-05 |
| [CR-0005](cr0005.md) | Replace placeholder brand icon with Agent Crew logo | P3 | Implemented | design-change | — (standalone asset swap) | 2026-06-09 |
| [CR-0006](cr0006.md) | Cull dead and no-op options-flow controls | P2 | Implemented | design-change | — | 2026-06-09 |
| [CR-0007](cr0007.md) | Options-flow usability restructure | P2 | Implemented | production-feedback | — | 2026-06-09 |
| [CR-0008](cr0008.md) | Re-baseline to bridge v4.141 + capability audit | P1 | Implemented | spec-gap | — | 2026-06-09 |
| [CR-0009](cr0009.md) | Surface bridge usage/cost and fleet doctor in HA | P2 | Implemented | feature-request | — | 2026-06-09 |
| [CR-0010](cr0010.md) | Agent memory record/recall from Home Assistant | P2 | Implemented | feature-request | — | 2026-06-09 |
| [CR-0011](cr0011.md) | Full PRD/TRD/TSD reconcile to post-EP0008/CR-0010 reality | P3 | Proposed | spec-gap | — | 2026-06-09 |
| [CR-0012](cr0012.md) | Make the fleet-doctor repair issue opt-in (default off) | P2 | Implemented | production-feedback | — | 2026-06-09 |
| [CR-0013](cr0013.md) | Options-flow refinements — remove Caller ID + Voice debug; session preset dropdown | P3 | Implemented | production-feedback | — | 2026-06-09 |
| [CR-0014](cr0014.md) | Harden the inbound webhook (local-only, POST-only, validated payloads, persistent id) | P2 | Implemented | design-change | — | 2026-07-04 |
| [CR-0015](cr0015.md) | URL-encode path parameters in the bridge client | P3 | Implemented | design-change | — | 2026-07-04 |
| [CR-0016](cr0016.md) | Service-layer and setup polish (default-agent parity, service errors, dead sensor, self-signed onboarding) | P3 | Implemented | design-change | — | 2026-07-04 |

## Dependencies

| CR | Depends On | Dependency Status |
| --- | --- | --- |
| CR-0001 | BG0001, BG0002 | Fixed, Fixed |
| CR-0002 | EP0002, EP0004 | Done, Done |
| CR-0003 | — | — |
| CR-0004 | EP0007 | Review |
| CR-0005 | — | — |
| CR-0006 | — | — |
| CR-0007 | CR-0006 | Implemented |
| CR-0008 | — | — |
| CR-0009 | CR-0008 | Implemented |
| CR-0010 | CR-0008 | Implemented |
| CR-0011 | CR-0014, CR-0015, CR-0016 | Sequencing — docs reconcile runs after the code CRs land |
| CR-0014 | BG0014 | Fixed |

## Notes

- CRs are numbered globally (CR-0001, CR-0002, etc.)
- Priority: P1 (critical gap) > P2 (important) > P3 (desirable) > P4 (nice to have)
- Types: feature-request, production-feedback, spec-gap, retrospective, design-change
- **CR-0002 supersedes CR-0001** — the one-entry-per-agent workaround was replaced by `ConversationEntity` + config subentries. CR-0001 stays `Proposed` (never actioned) for the historical record.
- CR-0002 and CR-0003 are both realised through **EP0007**. CR-0002 stays `Review` while US0021/US0027/US0031 are operator-gated; CR-0003 is `Implemented` (261 tests green) and addressed [BG0003](../bugs/BG0003-picker-lists-models-and-non-agents.md).
- **CR-0004** is realised through **EP0008** (conversation capability expansion, post-0.4.0). Transport decision: stay REST, no ACP. One minor release per phase; reconcile + full review at each phase close.
- **CR-0005** is a standalone cosmetic asset swap (Agent Crew brand icon at HA-standard sizes). No epic, no code/test impact; proposed and implemented in the same change.
- **CR-0006** and **CR-0007** came out of an options-flow "earn its place" review (2026-06-09). CR-0006 culls dead/no-op controls (the agent now actuates via its own `/api/mcp` mount, so the HA-side tool loop and its checkbox are dead); CR-0007 restructures the survivors for usability and depends on CR-0006 landing first.
- **CR-0008, CR-0009, CR-0010** came out of an inverse review (2026-06-09): what bridge capabilities the integration doesn't yet surface. The integration is baselined against bridge v4.36 but the live bridge is v4.137, so CR-0008 (re-baseline + capability audit, P1) is the hygiene gate; CR-0009 (usage/cost + doctor) and CR-0010 (agent memory) build on it. Proactive (US0037) and multimodal (US0035/38) were already covered by EP0008 and deliberately not re-filed; async long-running tasks (`POST /v1/messages`) is parked as a future candidate (noted in CR-0008).
- **CR-0014, CR-0015, CR-0016** came from the operator-requested full code + security review of 0.11.0 (2026-07-04), alongside bugs BG0012–BG0015. CR-0014 is the security priority (the webhook is the one unauthenticated inbound surface); CR-0015 and CR-0016 are hardening/polish. Related: BG0014 fixes the webhook crash path that CR-0014's validation items sit behind.
- Status values in use: `Proposed` | `Review` | `Implemented` | `Rejected` | `Deferred`. Use `/sdlc-studio cr close --cr CR-NNNN` to move a CR to a terminal state.
