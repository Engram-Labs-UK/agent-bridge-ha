# US0001: Project Scaffold

> **Status:** Done
> **Epic:** [EP0001: Bridge Foundation](../epics/EP0001-bridge-foundation.md)
> **Owner:** Darren Benson
> **Created:** 2026-04-05

## User Story

**As a** developer setting up the integration
**I want** the project structure, constants, and manifest in place
**So that** all subsequent modules have a stable foundation to build on

## Context

First story in the project. Creates the directory structure, constants module, manifest, HACS config, and translation files. Every other story depends on this.

---

## Acceptance Criteria

### AC1: Directory structure
- **Given** an empty custom_components/ directory
- **When** this story is implemented
- **Then** custom_components/agent_bridge/ exists with __init__.py, const.py, manifest.json, strings.json, translations/en.json, hacs.json at project root

### AC2: Constants module
- **Given** the const.py file
- **When** imported by any module
- **Then** DOMAIN, PLATFORMS, all CONF_* keys, all DEFAULT_* values, MAX_ENTITIES, MAX_TEXT_DEPTH, EVENT_* types, and TEXT_PRIORITY_KEYS are available (matching TRD Section 8a)

### AC3: Manifest
- **Given** manifest.json
- **When** HA discovers the integration
- **Then** domain is "agent_bridge", config_flow is true, iot_class is "local_polling", requirements is empty, version is "0.1.0" (matching TRD Section 8)

### AC4: Translations
- **Given** strings.json and translations/en.json
- **When** the config flow renders
- **Then** all step titles, field labels, and error messages render in English (matching TRD Section 8a strings table)

---

## Scope

### In Scope
- `custom_components/agent_bridge/const.py`
- `custom_components/agent_bridge/manifest.json`
- `custom_components/agent_bridge/__init__.py` (minimal -- just PLATFORMS constant, setup/unload stubs)
- `custom_components/agent_bridge/strings.json`
- `custom_components/agent_bridge/translations/en.json`
- `hacs.json` (project root)

### Out of Scope
- Bridge client (US0002)
- Config flow logic (US0004)
- Coordinator (US0005)

---

## Technical Notes

const.py must match TRD Section 8a exactly. The __init__.py stub should define async_setup_entry and async_unload_entry as no-ops that will be filled in by US0005. strings.json and translations/en.json must have identical structure per HA convention.

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| HA loads integration with no config entry | Integration loads without error, does nothing |
| manifest.json missing required field | HA rejects integration at load time (caught by HA validation) |

---

## Test Scenarios

- [ ] const.py: DOMAIN equals "agent_bridge"
- [ ] const.py: PLATFORMS contains sensor, binary_sensor, event
- [ ] const.py: all DEFAULT_* values match PRD defaults
- [ ] const.py: TEXT_PRIORITY_KEYS is ("text", "content", "message", "output_text")
- [ ] manifest.json: valid JSON with all required fields
- [ ] strings.json: contains config.step.user and config.step.agents sections
- [ ] __init__.py: async_setup_entry returns True
- [ ] __init__.py: async_unload_entry returns True

---

## Dependencies

### Story Dependencies
None -- first story.

### External Dependencies
| Dependency | Type | Status |
|------------|------|--------|
| Home Assistant Core 2025.1.0+ | Framework | Available |

---

## Estimation

**Story Points:** 2
**Complexity:** Low

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-04-05 | Claude | Initial story generation |
