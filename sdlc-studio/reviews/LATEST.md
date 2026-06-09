# Agent Bridge HA — current state (orientation anchor)

> Interim anchor. The authoritative current state is `/sdlc-studio status` plus the
> specs in `sdlc-studio/`. This file is rewritten by every `/sdlc-studio review`.

- **Version:** 0.9.0 (2026-06-05). Tested against Home Assistant 2026.2.3 / Python 3.13 (`const.TESTED_HA_VERSION`, pinned in CI). 261+ tests green.
- Reactive path on `ConversationEntity` + `ChatLog` (one entity per agent via config subentries); actuation via the agent's own `/api/mcp` mount (Option A), with deny/confirm list + fail-closed exposure + an `EVENT_ACTUATION_AUDIT` hook.

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
