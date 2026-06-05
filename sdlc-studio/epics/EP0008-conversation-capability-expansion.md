# EP0008: Conversation Capability Expansion (continuity, proactive, multimodal)

> **Status:** Review — all 8 stories implemented across 0.5.0–0.9.0. Done: US0032, US0034,
> US0035, US0036, US0037, US0039. Review (gated): US0033 (streaming, live-validation), US0038
> (Telegram image — bridge PR #42 + outbound-attachment routing follow-up).
> **Owner:** Darren Benson
> **Reviewer:** --
> **Created:** 2026-06-05
> **Target Release:** 0.5.0 – 0.10.0 (one minor per phase)
> **Change Request:** [CR-0004](../change-requests/cr0004.md)
> **Depends on:** EP0007 (reactive path on ConversationEntity + ChatLog), 0.4.0 caller_context

## Summary

Adopt the bridge REST capabilities the integration already could use but doesn't, and close the
gaps vs the HA LLM ecosystem (vision, proactive speech, AI Task). Transport stays REST (no
inbound ACP server exists; REST already carries session/streaming/attachments/proactive). Shaped
by a competitive survey, HA dev-docs, and live consults with the Cora agent — who reprioritised
vision up (safety) and AI Task down (defer), and asked us to measure session persistence before
building it (we did: the bridge already persists session by channel, 24h TTL).

## Inherited Constraints

| Source | Type | Constraint | Impact |
|--------|------|------------|--------|
| CR-0004 | Architecture | Stay REST; no ACP | Wire unused REST features, not a new transport |
| Phase 0 | Finding | Bridge persists session by channel (24h TTL) | Fix the channel key, don't build a session store |
| CR-0002 | Architecture | Agent self-actuates via `/api/mcp` (Option A) | No HA `llm.Tool` round-trip; confirm flow stays in the turn loop |
| Project | Process | Live-agent consult mandatory for agent-facing design | Cora consulted twice; her ranking drives phase order |
| Project | Process | Generated/feature specs carry `Verify:` AC; CI-gated | Local suites can't fully run (Python 3.13) — see lessons |
| Project | Process | Reconcile + full review at the end of each phase | Per-phase release gate |

---

## Phasing

- **P0 — spike (done):** US-spike folded into [Phase 0 plan]; outcome recorded in CR-0004.
- **P1 — continuity foundation:** US0032 (session) → US0033 (streaming) → US0034 (grounding++).
- **P2 — multimodal + safety:** US0035 (vision) → US0036 (confirm-before-actuate).
- **P3 — proactive + outbound media:** US0037 (announcements) → US0038 (Telegram image, + bridge PR).
- **P4 — generation:** US0039 (AI Task, scoped).

## Stories

| ID | Title | Status | Depends on | Phase | Target |
|----|-------|--------|-----------|-------|--------|
| [US0032](../stories/US0032-session-continuity-idle-channel.md) | Session continuity via idle-windowed channel key | Done | none | P1 | 0.5.0 |
| [US0033](../stories/US0033-response-streaming-tts.md) | Response streaming to TTS (deltas) | Review | US0032 | P1 | 0.6.0 |
| [US0034](../stories/US0034-richer-grounding-envelope.md) | Richer grounding: recent changes + presence + alarms/calendar | Done | none | P1 | 0.6.0 |
| [US0035](../stories/US0035-camera-vision-input.md) | Camera/vision input via image attachments | Done | none | P2 | 0.7.0 |
| [US0036](../stories/US0036-confirm-before-actuate.md) | Confirm-before-actuate (pendingAction + timeout + severity) | Done | US0032 | P2 | 0.7.0 |
| [US0037](../stories/US0037-proactive-announcements.md) | Proactive announcements to satellites (HA-as-client) | Done | none | P3 | 0.8.0 |
| [US0038](../stories/US0038-agent-telegram-camera-snapshot.md) | Agent → Telegram camera snapshot (+ bridge sendPhoto) | Review | US0035 | P3 | 0.9.0 |
| [US0039](../stories/US0039-ai-task-platform.md) | AI Task platform (generate_data, scoped) | Done | none | P4 | 0.9.0 |

## Execution Order

1. US0032 (session) → US0033 (streaming) → US0034 (grounding++)
2. US0035 (vision) → US0036 (confirm)
3. US0037 (proactive) → US0038 (Telegram image + bridge PR)
4. US0039 (AI Task)

## Notes

- One minor release per phase; reconcile + full review at each phase close (goal directive).
- US0038 requires a co-requisite `agent-bridge` PR (Telegram outbound `sendPhoto`); the HA side
  ships behind it. OpenClaw agents (Cora) have a `camera_snap`+`notify` shortcut today.
