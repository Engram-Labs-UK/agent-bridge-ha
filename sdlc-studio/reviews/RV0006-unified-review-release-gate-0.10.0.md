# RV0006 — Unified review (release gate for 0.10.0)

**Date:** 2026-06-09
**Trigger:** About to tag 0.10.0 (release gate).
**Scope:** PRD · TRD · TSD · CODE (Persona skipped — no `sdlc-studio/personas/`). Four legs fanned out as parallel review agents.

## Verdict

**Release-ready for 0.10.0 after the one code blocker is fixed.** The CODE leg (non-negotiable) found **no runtime defects** in the changed paths — the single blocker was `manifest.json` still on `0.9.0` (fixed → `0.10.0`). PRD/TRD/TSD are stale versus the shipped code (pre-existing debt since 2026-04-05); the actively-misleading claims were corrected this pass and the full reconcile is tracked in **CR-0011**.

## Leg findings

### CODE (non-negotiable) — PASS
- Audited CR-0006 cull fallout, CR-0009 (sensors/coordinator/diagnostics/doctor-repair), CR-0010 (memory), BG0005 (naming). All None-safe, async-safe, device identifiers consistent (`(DOMAIN, entry_subentry)`), per-agent usage failure isolated, redaction correct, no dangling imports.
- **Blocker (fixed):** `manifest.json` version `0.9.0` → `0.10.0`.

### PRD — stale, corrected
- Marked superseded: "HA Service Execution" feature + ACs, the `agent_bridge_tool_invoked` event AC, the removed options (`context_strategy`, `enable_tool_calls`, `enable_per_agent_entities`). Added Usage & Cost Sensors (CR-0009) + Agent Memory Services (CR-0010) to the inventory. Added the 0.10.0 §11 changelog entry. Full §3/§7 feature-detail + data models → CR-0011.

### TRD — stale, corrected
- Added a currency note (post-CR-0006..0010 deltas); marked §4 tool-execution + ADR-005 SUPERSEDED (agent-owned `/api/mcp` actuation). Full endpoint/CoordinatorData/module/ADR reconcile → CR-0011.

### TSD — stale, corrected
- Added a currency note (removed `test_tool_executor.py`/`test_init.py` + the tool-execution objective; new `test_diagnostics`/`test_openapi_contract` + extended suites). Full test-tree/module-table reconcile → CR-0011.

## Cross-document consistency
- PRD↔code: the removed tool loop is now consistently marked superseded across PRD/TRD/TSD + `AGENTS.md` Rule 4.
- Bridge baseline `4.141.0` consistent across `const.py`, TRD, TSD, LATEST.
- CR index reconciled: 7 Implemented, 1 Deferred (CR-0001), 1 Proposed (CR-0011), 2 Review (CR-0002/0004, component-complete). Bugs: 0 open.

## Priority actions
1. **[done]** `manifest.json` → 0.10.0.
2. **[done]** Correct the actively-false PRD/TRD/TSD claims + changelogs.
3. **[tracked: CR-0011]** Full PRD/TRD/TSD feature/interface/test expansion.
4. Tag 0.10.0 + publish the GitHub release.
