# EP0007 / CR-0002 — Implementation Kickoff (new-session brief)

> **Created:** 2026-06-01 by Claude (in the agent-bridge session). **Read this first**, then `change-requests/cr0002.md` + `epics/EP0007-bridge-v436-modern-ha-realignment.md` + `stories/US0021-actuation-strategy-spike.md` (spike outcome). Planning is **done**; this session is for **implementation**.

## What this is
`agent-bridge-ha` (v0.1, targets bridge "v3.1.0+") has drifted against bridge **v4.36** + modern HA. A verified multi-agent audit found the **reactive HA path is structurally inert** (agents reply but never actuate) for two root causes: **(G1)** no `tool_calls` contract on the bridge *or* from HA, and **(G2)** the component is on HA's legacy `AbstractConversationAgent`. CR-0002 + EP0007 (10 stories) re-platform it onto HA's `ConversationEntity`/`ChatLog` + agent-direct HA actuation.

## Decisions already made (don't re-litigate)
- **Actuation = Option A, refined (agent-direct + shared envelope + audit events).** The conversation entity forwards the utterance + an entity **grounding hint** (hint, *not* authority) as **free text**; **the agent actuates HA itself** via a **shared HA mount** (the DBee `/api/mcp` HA-MCP-Server pattern), reads live state back to confirm, and **emits an actuation event to the bridge audit log** (one audit surface — Rule 3). NOT a bridge `tool_calls` round-trip; NOT conversation-entity-provides-`llm.Tool`. See US0021 Spike Outcome for why.
- **Retire `exposure.py` + `tool_executor.py`** — entity context + tools move to the agent's HA mount (also kills the fail-open exposure bug).
- **DBee-first** — prove the reactive path end-to-end with DBee (already `/api/mcp`-mounted), then provision Cora/Eve/Julian.
- **Agent selection is in-app** (HA config UI / US0025 config subentries), operator-selectable. Seed set: **Cora, Eve, Julian, DBee**.
- **Deny/confirm list** for risky domains (locks, alarms, heating, external doors).
- **Validation:** pytest here (no env yet — set up `.venv` + `pytest` + `pytest-homeassistant-custom-component`; Python **3.12.3** present) + operator runs manual E2E on the live HA (10.0.0.209; password-auth, not reachable from the agent session).

## Live-fleet consult (2026-06-01, mandatory gate — done)
- **HA tools today:** Cora **none** (only openclaw `nodes_*`), Eve **none**, Julian **none**, **DBee yes** (`/api/mcp`, live-verified). ⇒ shared HA mount must be **provisioned per harness** for Cora/Eve/Julian.
- **Julian:** define the HA capability **once** (shared envelope, avoid divergence) + **audit-event emission** (avoid fragmentation/Rule-3 bypass) + read-back.
- **Eve:** per-agent creds, idempotent calls, structured receipts, deny/confirm list.
- **Cora:** prefers a fast entity-resolver + live state-fetch over a stale prompt snapshot.

## Sequencing
1. **P0 (no deps — start now, TDD):** US0022 (`tools.invoke` `{agent,tool,args}` + `broadcast` `{messages[],tags}`+responses-object), US0023 (SSE `event:message {text}`+`event:done`; stop swallowing errors), US0024 (webhook `{agentId,healthy}` + full event catalogue incl. `bridge:upgraded`).
2. **US0021** — decision RECORDED (this brief); **AC2 still open**: needs the operator's live HA reactive-turn logs (OQ2) to confirm the dominant failure symptom.
3. **Re-platform (DBee-first):** US0025 (`ConversationEntity` + config subentries) → US0026 (`_async_handle_message` + `ChatLog`) → **US0027** (DBee-first reactive proof per the decided design — free-text forward + grounding hint + reply + actuation-audit surfacing; NOT a bridge tool_calls round-trip).
4. **US0028** (v4.36 discovery/health surface; in-app agent selection seeded Cora/Eve/Julian/DBee + `x-bridge-mcp-caller` identity), **US0029** (drift defences + HA-version pin + CI), **US0030** (docs/README/TRD to v4.36 + reactive/proactive boundary).
5. **US0031 (TO CREATE):** Shared HA tool envelope + actuation audit-events + fleet provisioning (the shared `/api/mcp` mount across Cora/Eve/Julian harnesses + the bridge audit-event path; decide existing bridge audit tool vs a small `agent-bridge` CR).

## Open items for the operator
- **Live HA reactive-turn logs** (US0021 AC2 / OQ2).
- Provisioning the shared HA mount into Cora (openclaw) / Eve (codex) / Julian (claude-code) harnesses — harness-side, mirrors DBee's `~/.hermes/config.yaml` `mcp_servers.homeassistant` (`url: http://10.0.0.209:8123/api/mcp`, Streamable HTTP, `Bearer ${HASS_TOKEN}`).
- Audit-event mechanism: reuse an existing bridge audit tool (e.g. `bridge_mark_critical_audit_event`) or a small dedicated `agent-bridge` CR (US0031).

## Test-env setup (one-time)
```bash
cd agent-bridge-ha
python3 -m venv .venv && . .venv/bin/activate
pip install -U pip
pip install pytest pytest-homeassistant-custom-component homeassistant   # pin to the version in pyproject/HA floor
python -m pytest tests/ -q
```

---

## Component-complete close — external gates (2026-06-09, Wave 5 reconcile)

The autonomous code-health + backlog-closure pass (CR-0005..CR-0010, BG0005) is shipped and CI-green. Every in-repo item is closed. Two CRs remain **component-complete** — all HA-side code is done, only irreducibly-external work is outstanding. These are tracked here, not as open HA bugs:

**CR-0002 / EP0007** (reactive realignment — component code done, 248+ tests green):
- **US0021 AC2** — operator captures a live HA reactive-turn log on 10.0.0.209 (information-gathering; no code).
- **US0027 AC2/AC3** — operator runs the live "turn on the lights" E2E with DBee + confirms actuation-audit events reach the bridge (reuse `bridge_mark_critical_audit_event`).
- **US0031 AC3** — provision the shared `/api/mcp` mount into the Cora/Eve/Julian harnesses (other repos), then per-agent E2E.

**CR-0004 / EP0008** (conversation expansion — 6/8 stories Done, code shipped):
- **US0033 AC2** — human perception that streaming lowers TTS latency on the live install (irreducibly human).
- **US0038 AC2** — bridge PR #42 outbound-attachment routing (agent reply image → Telegram `sendPhoto`) merges, then live E2E.

None of these can be done by editing `agent-bridge-ha` alone. The component code is complete and merged; closing them is gated on the live deploy, human sign-off, or the cross-repo bridge PR above. They are deliberately left in `Review` rather than marked Implemented so no external AC is falsely claimed as verified.

**Also pending the next deploy** (code in `main`, live install runs 0.9.0): BG0005 friendly-name fix, CR-0007 options UI, CR-0009 usage/cost sensors + doctor diagnostics, CR-0010 memory services. Confirm on the live install after a HACS update.
