# Agent Bridge HA — current state (orientation anchor)

> Interim anchor. The authoritative current state is `/sdlc-studio status` plus the
> specs in `sdlc-studio/`. This file is rewritten by every `/sdlc-studio review`.

- **Version:** 0.9.0 manifest (next release ~0.10.0 — see "Merged, unreleased"). Tested against Home Assistant 2026.2.3 / Python 3.13 (`const.TESTED_HA_VERSION`, pinned in CI) and **bridge v4.141.0** (`const.TESTED_BRIDGE_VERSION`, re-baselined CR-0008). CI green per wave.
- Reactive path on `ConversationEntity` + `ChatLog` (one entity per agent via config subentries); actuation via the agent's own `/api/mcp` mount (Option A), with deny/confirm list + fail-closed exposure + an `EVENT_ACTUATION_AUDIT` hook. There is **no HA-side tool loop** (CR-0006 removed the dead one; `AGENTS.md` Rule 4 reflects this).

## Merged, unreleased (autonomous code-health pass, 2026-06-09 — live install still runs 0.9.0)

- **CR-0006** cull of the dead HA-side tool subsystem + dead constants + `SessionManager`; coordinator `NotRequired` fix.
- **BG0005** conversation/AI-task entities named `name (crew)` from discovery, never the raw agent id (shared `helpers.agent_label`).
- **CR-0007** options form regrouped into essentials + a collapsed Advanced section; all fields labelled, with help text + ranges.
- **CR-0008** re-baseline to bridge v4.141 + `message:sent` webhook + an OpenAPI contract test.
- **CR-0009** per-agent token + cost (GBP) sensors, `diagnostics.py` (fleet doctor + redaction), `fleet_doctor` repair issue.
- **CR-0010** `agent_bridge.memory_record` / `memory_recall` services.
- **BG0001 / BG0002** confirmed resolved by EP0007 and closed; **CR-0001** deferred (superseded by the subentry model). Backlog now: 0 open bugs; the only non-terminal CRs are CR-0002/CR-0004, component-complete and external-gated.

## Shipped (EP0008 capability phases, on the EP0007 v4.36 re-platform)

- **0.9.0** AI Task platform — one `ai_task` entity per agent (`ai_task.generate_data`).
- **0.8.0** Proactive announcements — `agent_bridge.announce` on a chosen `assist_satellite` with priority.
- **0.7.0** Camera/vision input (`agent_bridge.ask_with_image`) + confirm-before-actuate (`[confirm:LEVEL]`).
- **0.6.0** Opt-in response streaming to TTS + a richer grounding envelope.
- **0.5.0** Session continuity — idle-windowed channel key `ha:{agent_id}:{scope}:{epoch}`.
- **0.4.0** Structured `caller_context` (source / speaker / area+floor / local time) block.
- **0.2.0-0.3.2** EP0007 / CR-0002 re-align to bridge v4.36 + modern HA; crew-scoped agent picker (CR-0003); caller-id 403 fix (BG0004).

## Operator-gated remainder (cannot be done from this repo - see `IMPLEMENTATION-KICKOFF.md` + the EP0007 epic)

- **US0021** live reactive-turn logs.
- **US0027** live "turn on the lights" E2E on the live HA (10.0.0.209).
- **US0031** provision the shared `/api/mcp` mount into Cora / Eve / Julian harnesses + confirm the bridge audit-event wiring.

## Older history

`git log` (per-commit narrative) + PRD §11 ChangeLog.
