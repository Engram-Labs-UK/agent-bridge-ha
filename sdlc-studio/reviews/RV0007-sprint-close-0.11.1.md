# RV0007 — Sprint-close unified review (0.11.1, SPRINT-2026-07-04)

> **Scope:** the sprint increment on `fix/backlog-clear-0.11.1` (BG0012–BG0015, CR-0011, CR-0014–CR-0016) against PRD · TRD · TSD · CODE.
> **Verdict: GREEN** for tagging 0.11.1, subject to the standing operator-gated items (below).

## CODE leg

- Independent adversarial critic (separate agent instance, did not author the diff): **8/8 APPROVE** — full depth on BG0012 (parser: ~4,000-chunking property probe vs the `_parse_confirm_marker` oracle, all consistent) and CR-0014 (security: registration kwargs verified against the installed HA 2026.2.3 API, push-validation bypass hunt, listener-ordering audit); light independent pass on the mechanical units. Verdicts committed in `reviews/critic-verdicts.md`.
- One critic finding actioned in-sprint: the CR-0014 risk-table mitigation (unregister + re-register on a registration collision) was implemented with a regression test.
- Gate: 369 tests green (was 326), ruff lint + format clean, mypy at the pre-existing 16-error baseline (mypy is not a CI gate; the baseline is unchanged by this sprint).
- Non-blocking observations and their rulings are in `decisions/SPRINT-2026-07-04.md`.

## PRD / TRD / TSD legs

- CR-0011 reconciled all three docs to the shipped code (929 insertions / 558 deletions), verified claim-by-claim against source by the authoring pass and spot-checked by a separate reviewer instance.
- PRD: Option A actuation rewritten in place (no strike-through supersessions remain); usage/cost, fleet-doctor, diagnostics, memory, AI-task features now carry ACs + data models; §11 ChangeLog current to 0.11.1.
- TRD: client-method ↔ endpoint map (incl. CR-0015 encoding note), CoordinatorData `NotRequired` fields, webhook lifecycle (CR-0014), **ADR-006** (agent-owned `/api/mcp` actuation) supersedes ADR-005.
- TSD: test tree and module table match `tests/` exactly (19 test files + fixtures); tool-execution objective gone.
- `reconcile detect`: **drift 0** across all artifact types.

## Backlog state after this sprint

- Bugs: **0 open** (15 total, all Fixed).
- CRs: **0 Proposed** — 13 Implemented, 2 Review (CR-0002/CR-0004, component-complete, operator/cross-repo-gated), 1 Deferred (CR-0001, historical).
- The only outstanding work is the operator-gated remainder: US0021 (live reactive-turn logs), US0027 (live E2E), US0031 (`/api/mcp` mount provisioning) — see `IMPLEMENTATION-KICKOFF.md`.

## Pre-release gate status (AGENTS.md)

1. `reconcile` drift 0 ✅ (per-story `Verify:` DSL execution unchanged by this sprint — sprint units are bugs/CRs, verified via their own test-backed clauses)
2. Unified review incl. CODE leg ✅ (this document)
3. Retro exists ✅ (`retros/RETRO0001-sprint-2026-07-04.md`)

**Hand-back:** tagging/releasing 0.11.1 (HACS) and the live-install update are operator actions — not performed by the sprint loop. Note for the release notes: `send_message`/`ask_with_image` without `agent_id` now target the configured default agent (CR-0016, documented-behaviour convergence).

## Upstream action (not this repo)

- sdlc-studio skill defect: `audit.py check` bug-readiness headings disagree with `templates/core/bug.md` (flags every template-authored bug "underspecified"). Recorded in RETRO0001 lesson 1 and the decisions ledger.
