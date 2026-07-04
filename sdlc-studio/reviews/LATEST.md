# Agent Bridge HA — current state (orientation anchor)

> Most recent review: **RV0007** (sprint-close for 0.11.1, 2026-07-04) — see
> `reviews/RV0007-sprint-close-0.11.1.md`. This file is rewritten by every
> `/sdlc-studio review`; authoritative state is `/sdlc-studio status` + the specs.

- **Version:** **0.11.1** (manifest bumped; tag/release is operator-gated). Tested against Home Assistant 2026.2.3 / Python 3.13 (`const.TESTED_HA_VERSION`, pinned in CI) and **bridge v4.141.0** (`const.TESTED_BRIDGE_VERSION`). Suite 369 green; ruff clean.
- **0.11.1 (SPRINT-2026-07-04 backlog clear, from the operator-requested full code + security review):**
  - **BG0012** streaming `[confirm:LEVEL]` marker now stripped *before* deltas reach TTS/ChatLog (severity via holder); **BG0013** `extract_response_text` fails soft on malformed `choices`; **BG0014** webhook 400s non-object JSON; **BG0015** options-flow discovery sends the caller header.
  - **CR-0014** webhook hardening: local-only + POST-only registration, pushed-value validation (status whitelist, typed health shape), persistent webhook id (HA `CONF_WEBHOOK_ID`) + stale-subscription cleanup + collision fallback, id logged at DEBUG only.
  - **CR-0015** client URL-encodes path-interpolated ids. **CR-0016** `send_message`/`ask_with_image` default-agent fallback (**behaviour change** — release-notes item), `ServiceValidationError`, dead `PerAgentHealthSensor` culled, first-run "Verify SSL certificate" toggle.
  - **CR-0011** full PRD/TRD/TSD reconcile; **ADR-006** (agent-owned `/api/mcp` actuation) supersedes ADR-005.
  - Process: TDD red-first per unit; independent critic 8/8 APPROVE; decisions in `decisions/SPRINT-2026-07-04.md`; retro `retros/RETRO0001-sprint-2026-07-04.md`.
- **Backlog:** 0 open bugs, 0 proposed CRs. Non-terminal: CR-0002/CR-0004 (Review, component-complete, operator/cross-repo-gated), CR-0001 (Deferred, historical).
- Reactive path on `ConversationEntity` + `ChatLog` (one entity per agent via config subentries); actuation via the agent's own `/api/mcp` mount (Option A), deny/confirm + fail-closed exposure + `EVENT_ACTUATION_AUDIT`. **No HA-side tool loop** (ADR-006).

## Operator-gated remainder (cannot be done from this repo — see `IMPLEMENTATION-KICKOFF.md` + EP0007)

- **US0021** live reactive-turn logs.
- **US0027** live "turn on the lights" E2E on the live HA (10.0.0.209).
- **US0031** provision the shared `/api/mcp` mount into Cora / Eve / Julian harnesses + confirm the bridge audit-event wiring.
- **Release 0.11.1**: operator tags + updates the live install (live install runs 0.9.0 per RV0006-era note; confirm on deploy).

## Upstream (not this repo)

- sdlc-studio skill: `audit.py check` bug-readiness headings disagree with `templates/core/bug.md` (every template-authored bug flags "underspecified") — RETRO0001 lesson 1.

## Older history

`git log` (per-commit narrative) + PRD §11 ChangeLog. Previous anchor: RV0006 (release-gate 0.10.0).
