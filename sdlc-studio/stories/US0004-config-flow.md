# US0004: Config Flow

> **Status:** Done
> **Epic:** [EP0001: Bridge Foundation](../epics/EP0001-bridge-foundation.md)
> **Owner:** Darren Benson
> **Created:** 2026-04-05

## User Story

**As** Darren
**I want** to set up the integration via the HA UI by entering the bridge URL and token, then selecting which agents to expose
**So that** setup is guided and validated

## Context

Two-step config flow: (1) bridge URL + token with connectivity/auth validation, (2) agent selection from discovery. Plus an options flow for post-setup changes.

---

## Acceptance Criteria

### AC1: Step 1 - Connection
- **Given** the user enters bridge URL and token
- **When** they submit step 1
- **Then** the flow validates connectivity (GET /health) and auth (GET /v1/discovery), showing specific errors for each failure mode

### AC2: Step 2 - Agent selection
- **Given** step 1 passed
- **When** step 2 renders
- **Then** discovered agents are shown with names and the user selects default_agent and voice_agent

### AC3: Config entry creation
- **Given** both steps complete
- **When** the flow finishes
- **Then** a config entry is created with bridge_url, bridge_token, default_agent, voice_agent, and all option defaults

### AC4: Options flow
- **Given** a configured integration
- **When** the user opens options
- **Then** they can change: default_agent, voice_agent, context_max_chars, context_strategy, enable_per_agent_entities, enable_tool_calls, thinking_timeout, ssl_verify, debug_logging

### AC5: Error display
- **Given** bridge is unreachable
- **When** step 1 is submitted
- **Then** "Cannot connect to bridge" error is shown (not a stack trace)

---

## Scope

### In Scope
- `custom_components/agent_bridge/config_flow.py`
- Step user: URL + token input with validation
- Step agents: agent selection from discovery
- Options flow: all configurable settings
- Error handling: cannot_connect, invalid_auth

### Out of Scope
- Bridge client implementation (US0002 -- imported)
- Coordinator setup (US0005)

---

## Technical Notes

Config flow class extends `config_entries.ConfigFlow` with DOMAIN from const.py. Options flow extends `config_entries.OptionsFlow`. Step 1 creates a temporary BridgeClient to validate. voluptuous schemas for input validation. Default URL: `http://localhost:18780`.

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| Bridge URL missing scheme | Add http:// prefix |
| Bridge URL with trailing slash | Strip it |
| Bridge healthy but auth fails | Show "Invalid API token" |
| Bridge unreachable | Show "Cannot connect to bridge" |
| Discovery returns 0 agents | Show "No agents found" error |
| Options flow with bridge offline | Show cached agents from last discovery |

---

## Test Scenarios

- [ ] Step 1 happy path: URL + token → validates → shows step 2
- [ ] Step 1 auth failure: 401 → shows invalid_auth error
- [ ] Step 1 connection refused → shows cannot_connect error
- [ ] Step 1 timeout → shows cannot_connect error
- [ ] Step 2 shows discovered agents
- [ ] Step 2 creates config entry with correct data
- [ ] Options flow renders all options with current values
- [ ] Options flow saves changes to config entry
- [ ] Config entry has all required fields
- [ ] Config entry has correct defaults for optional fields

---

## Dependencies

### Story Dependencies

| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| [US0001](US0001-project-scaffold.md) | Hard | const.py, strings.json | Done |
| [US0002](US0002-bridge-client.md) | Hard | BridgeClient for validation | Done |

---

## Estimation

**Story Points:** 3
**Complexity:** Medium

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-04-05 | Claude | Initial story generation |
