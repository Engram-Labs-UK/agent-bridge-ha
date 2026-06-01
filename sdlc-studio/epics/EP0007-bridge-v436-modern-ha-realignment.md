# EP0007: Bridge v4.36 + Modern HA Re-Alignment

> **Status:** Proposed
> **Owner:** Darren Benson
> **Reviewer:** --
> **Created:** 2026-06-01
> **Target Release:** 0.2.0
> **Change Request:** [CR-0002](../change-requests/cr0002.md)
> **Depends on:** EP0002 (Conversation & Home Control), EP0004 (Multi-Agent)
> **Supersedes:** CR-0001

## Summary

Re-platform the **reactive** path (HA → bridge agent) onto Home Assistant's modern `ConversationEntity` + `ChatLog` model and re-align the bridge client to the **v4.36** contract, restoring live-agent home control (currently structurally inert — agents reply but never actuate). Per the **CR-0002 actuation decision (Option A, refined by the US0021 spike)**, the conversation entity forwards the utterance + an entity grounding hint as free text and **the agent actuates HA itself** via a shared `/api/mcp` HA-MCP mount (the DBee pattern), reading state back and emitting an actuation audit event — **not** the `async_provide_llm_data()`/`llm.Tool` round-trip (the bridge carries no `tool_calls`). So **no co-requisite `agent-bridge` CR is required** for actuation and the bespoke `exposure.py`/`tool_executor.py` path is retired.

## Inherited Constraints

| Source | Type | Constraint | Impact |
|--------|------|------------|--------|
| CR-0002 | Architecture | Actuation = agent-direct via shared `/api/mcp` HA mount (Option A, refined) | Retire bespoke exposure + tool-executor; no bridge tool_calls dependency; no `llm.Tool` round-trip |
| US0021 | Decision | Live-fleet consult done; agent-direct confirmed; fleet provisioning split to US0031 | Cora/Eve/Julian have no HA tools today — provision before they can be voice agents |
| Project | Process | Live-agent consult mandatory for agent-facing design | DBee-first proof (US0027); fleet provisioning gated on operator harness work (US0031) |
| Project | Process | Generated specs stay Proposed until tests pin them | Stories carry `Verify:` acceptance; no auto-promotion to Done |
| HA | Compatibility | Pin + CI against a current HA core | Prevents silent re-drift (the failure this epic fixes) |

---

## Phasing

- **P0 — contract re-alignment (no dependency, fast wins):** US0022, US0023, US0024 — restore the non-actuation surfaces (invoke/broadcast/SSE/webhook) immediately.
- **P1 — actuation root-cause:** US0021 (decision spike, validate Option A with live logs) → US0027 (the load-bearing DBee-first proof) → US0031 (generalise to the fleet).
- **P2 — modern HA re-platform:** US0025 (`ConversationEntity` + subentries) → US0026 (`_async_handle_message` + `ChatLog`).
- **P3 — v4.36 surface adoption + drift defences:** US0028, US0029, US0030.

## Stories

| ID | Title | Status | Depends on | Phase |
|----|-------|--------|-----------|-------|
| [US0021](../stories/US0021-actuation-strategy-spike.md) | Decision spike — validate Option A (HA LLM API/MCP) against live agents | Proposed | none | P1 |
| [US0022](../stories/US0022-bridge-client-invoke-broadcast-realign.md) | Re-align bridge client to v4.36 `tools.invoke` + `broadcast` | Done | none | P0 |
| [US0023](../stories/US0023-sse-streaming-failsafe.md) | Fix SSE streaming delta/terminal parsing + fail-safe error handling | Done | none | P0 |
| [US0024](../stories/US0024-webhook-payload-and-catalogue.md) | Webhook `agent:health-changed` payload + full event catalogue | Done | none | P0 |
| [US0025](../stories/US0025-conversationentity-subentries.md) | Migrate to `ConversationEntity` + config subentries | Proposed | US0021 | P2 |
| [US0026](../stories/US0026-handle-message-chatlog.md) | Implement `_async_handle_message` + adopt `ChatLog` | Proposed | US0025 | P2 |
| [US0027](../stories/US0027-restore-actuation-llm-api.md) | Restore reactive actuation — DBee-first proof (agent-direct) + fail-closed exposure | Proposed | US0026 | P1 |
| [US0028](../stories/US0028-v436-discovery-health-surface.md) | Adopt v4.36 discovery/health surface (caller header, health, metrics, taxonomy, `/v1/health`) | Proposed | US0025 | P3 |
| [US0029](../stories/US0029-drift-defences.md) | Drift defences — agent-context awareness, version pin, CI vs current HA | Proposed | US0024 | P3 |
| [US0030](../stories/US0030-docs-reactive-proactive-boundary.md) | Document reactive/proactive boundary + update README/TRD to v4.36 | Proposed | US0027 | P3 |
| [US0031](../stories/US0031-shared-ha-envelope-audit-fleet-provisioning.md) | Shared HA tool envelope + actuation audit-events + Cora/Eve/Julian provisioning | Proposed | US0027 | P1 |

## Execution Order

1. US0022 / US0023 / US0024 (P0 — parallel, no dependency)
2. US0021 (decision spike — needs operator live HA logs, OQ2)
3. US0025 → US0026 → US0027 (re-platform + DBee-first actuation proof)
4. US0028 (parallel with US0026/0027), US0029
5. US0031 (fleet provisioning + audit-events — operator/cross-repo gated), US0030 (final docs + reconciliation)

## Notes
- This epic supersedes the CR-0001 one-entry-per-agent workaround with the `ConversationEntity` + config-subentry model.
- Option A means `exposure.py` + `tool_executor.py` become fallback-only or are retired; the long-term boundary vs HA's `/api/mcp` MCP Server is OQ3.
