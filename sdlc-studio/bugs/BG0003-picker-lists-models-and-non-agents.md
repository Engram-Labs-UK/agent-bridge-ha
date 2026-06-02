# BG0003: Agent picker lists models, chatbots and workerbots — not just usable agents

> **Status:** Fixed
> **Severity:** Medium
> **Priority:** P2
> **Reporter:** Darren
> **Assignee:** Claude
> **Created:** 2026-06-02

## Summary

The agent-selection dropdowns (config flow `async_step_agents`, the conversation
subentry picker, and the options flow) were populated directly from `/v1/discovery`
with **no filtering**. The v4.36 bridge exposes 18+ entries including bare model
passthroughs (`openrouter-*`, `identitySubstrate: 'none'`), chatbots (conversational
but no tools — can't actuate) and workerbots (tools but not conversational), all of
which are useless as Home Assistant voice agents. They cluttered the picker and let an
operator pick something that cannot actuate the home.

## Affected Area

- **Epic:** [EP0007: Bridge v4.36 + Modern HA Re-Alignment](../epics/EP0007-bridge-v436-modern-ha-realignment.md)
- **Story:** [US0025](../stories/US0025-conversationentity-subentries.md) / [US0028](../stories/US0028-v436-discovery-health-surface.md)
- **Component:** config_flow.py (all pickers), conversation.py (entity gate)

## Root Cause

US0028 added capability gating for **entity creation** (`_is_voice_capable`) but it
was never applied to the **selection dropdowns**, and it allowed `chatbot`. The bridge
taxonomy (CR-0256) distinguishes `agentClass = agent | workerbot | chatbot` and
`identitySubstrate = engram | persona | none`; only `agentClass: 'agent'` has both
tools + conversational + identity.

## Fix

`helpers.is_selectable_agent(raw)` — include an agent only when it is not an
orchestrator, `agentClass == 'agent'` (or no taxonomy, for legacy bridges), and
`identitySubstrate != 'none'`. Applied to all three pickers **and** tightened the
entity-creation gate to match (chatbots no longer exposed). Verified by
`tests/test_agent_selection.py` (models/chatbots/workerbots/orchestrators excluded;
real persona/engram agents and legacy entries included).

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-06-02 | Claude | Filed + fixed on branch config-flow-agent-crew-filter |
