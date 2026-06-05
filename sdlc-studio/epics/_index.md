# Epic Registry

**Last Updated:** 2026-06-05
**PRD Reference:** [Product Requirements Document](../prd.md)

## Summary

| Status | Count |
|--------|-------|
| Draft | 0 |
| Proposed | 0 |
| Ready | 0 |
| Approved | 0 |
| In Progress | 1 |
| Review | 1 |
| Done | 6 |
| **Total** | **8** |

## Epics

| ID | Title | Status | Owner | Stories | Target |
|----|-------|--------|-------|---------|--------|
| [EP0001](EP0001-bridge-foundation.md) | Bridge Foundation | Done | Darren Benson | 5 | 0.1.0 |
| [EP0002](EP0002-conversation-and-control.md) | Conversation & Home Control | Done | Darren Benson | 5 | 0.1.0 |
| [EP0003](EP0003-observability-and-automation.md) | Observability & Automation | Done | Darren Benson | 4 | 0.1.0 |
| [EP0004](EP0004-multi-agent.md) | Multi-Agent Support | Done | Darren Benson | 3 | 0.1.0 |
| [EP0005](EP0005-realtime-and-broadcast.md) | Real-Time & Broadcast | Done | Darren Benson | 2 | 0.2.0 |
| [EP0006](EP0006-advanced-voice.md) | Advanced Voice | Done | Darren Benson | 1 | 0.2.0 |
| [EP0007](EP0007-bridge-v436-modern-ha-realignment.md) | Bridge v4.36 + Modern HA Re-Alignment | Review | Darren Benson | 11 | 0.2.0 |
| [EP0008](EP0008-conversation-capability-expansion.md) | Conversation Capability Expansion | In Progress | Darren Benson | 8 | 0.5.0–0.10.0 |

## Dependency Graph

```
EP0001 (Bridge Foundation)
  ├── EP0002 (Conversation & Control)
  │     ├── EP0003 (Observability & Automation)
  │     │     └── EP0004 (Multi-Agent)
  │     ├── EP0004 (Multi-Agent)
  │     └── EP0006 (Advanced Voice)
  ├── EP0003 (Observability & Automation)
  │     └── EP0005 (Real-Time & Broadcast)
  └── EP0005 (Real-Time & Broadcast)
```

## Execution Order

| # | Epic | Dependencies | Phase |
|---|------|-------------|-------|
| 1 | EP0001 | None | 0.1.0 |
| 2 | EP0002 | EP0001 | 0.1.0 |
| 3 | EP0003 | EP0001, EP0002 | 0.1.0 |
| 4 | EP0004 | EP0001, EP0002, EP0003 | 0.1.0 |
| 5 | EP0005 | EP0001, EP0003 | 0.2.0 |
| 6 | EP0006 | EP0001, EP0002 | 0.2.0 |
| 7 | EP0007 | EP0002, EP0004 | 0.2.0 |
| 8 | EP0008 | EP0007 | 0.5.0–0.10.0 |

## Notes

- Epics are numbered globally (EP0001, EP0002, etc.)
- Stories are tracked in [Story Registry](../stories/_index.md)
- EP0001-EP0004 are Phase 1 (v0.1.0) -- core functionality
- EP0005-EP0006 are Phase 2 (v0.2.0) -- enhancements
- EP0007 (CR-0002) is the v4.36 + modern-HA re-alignment; restores the reactive home-control path (actuation Option A refined: agent-direct via a shared `/api/mcp` HA mount, not an `llm.Tool` round-trip). Supersedes CR-0001.
- EP0008 (CR-0004) is the conversation capability expansion: session continuity, streaming, richer grounding, vision, confirm-before-actuate, proactive announcements, agent→Telegram image, AI Task. Stays on REST (no ACP); one minor release per phase, reconcile + full review at each phase close.
