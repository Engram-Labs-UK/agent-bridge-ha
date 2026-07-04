<!--
Template: Bug Report (Streamlined)
File: sdlc-studio/bugs/BG{NNNN}-{slug}.md
Status values: See reference-outputs.md
Related: help/bug.md, reference-bug.md
-->
# BG0016: CI installs hassil/home-assistant-intents unpinned — a newer intents release breaks the conversation import and fails every run

> **Status:** Fixed
> **Severity:** Medium
> **Priority:** P2
> **Reporter:** 0.11.1 release gate (PR #17 CI failure, 2026-07-04)
> **Assignee:** —
> **Created:** 2026-07-04
> **Verification depth:** functional

## Summary

`validate.yml` pins `homeassistant==${HA_VERSION}` but installs `hassil` and
`home-assistant-intents` unpinned. HA 2026.2.3's conversation component imports `FuzzyConfig`
from `home_assistant_intents`; the intents release stream has since moved (2026.6.24 at time of
failure), and the resolved latest no longer matches — `ImportError: cannot import name
'FuzzyConfig'` while loading `tests/conftest.py`, failing every CI run regardless of the diff
under test. The same drift was hit (and pinned around) when building the local venv for
SPRINT-2026-07-04; CI had simply not run since the ecosystem moved. This is the Critical Rule 9
class (version pins that must move together) extended to the conversation component's runtime
requirements.

**Verify:** CI `test` job passes on the pinned pair; the pins match the versions in the installed
HA's `homeassistant/components/conversation/manifest.json` (`hassil==3.5.0`,
`home-assistant-intents==2026.1.28` for HA 2026.2.3).

## Affected Area

- **Component:** `.github/workflows/validate.yml` (test job install step)
- **Origin:** EP0007 CI setup — correct at authoring time, broken by upstream release drift

## Environment

- **Version:** CI only; first observed on PR #17 (0.11.1 release gate)

---

## Reproduction Steps

1. Run the `test` workflow job after the intents package has published a release newer than the
   pinned HA's manifest expects (true as of 2026-07-04).
2. `pip install "homeassistant==2026.2.3" ... && pip install hassil home-assistant-intents ...`
3. `pytest tests/` → `ImportError: cannot import name 'FuzzyConfig' from 'home_assistant_intents'`
   during conftest import; the whole suite errors before collection.

## Expected Behaviour

CI resolves the dependency set the pinned HA actually declares, so a run tests the diff, not the
day's ecosystem state.

## Actual Behaviour

Every run fails at conftest import with the FuzzyConfig ImportError.

---

## Root Cause Analysis

HA loads component requirements at runtime, so pip-installing the components' packages is manual in
CI — and the manual line pinned only PyTurboJPEG. `hassil`/`home-assistant-intents` are tightly
coupled to the HA version via the conversation manifest; unpinned they track latest.

## Fix Description

Pin both to the HA 2026.2.3 conversation manifest versions (`hassil==3.5.0`,
`home-assistant-intents==2026.1.28`) with a comment binding them to `HA_VERSION` bumps (Critical
Rule 9 discipline). Local venv recipe already uses the same pins.

### Files Modified

| File | Change |
|------|--------|
| `.github/workflows/validate.yml` | pin `hassil==3.5.0`, `home-assistant-intents==2026.1.28` + bump-together comment |

---

## Verification

- [x] Fix verified: PR #17 CI `test` job green on the pinned pair (regression evidence: the same job red one commit earlier — seen-to-fail satisfied by the failing run itself)

**Verified by:** PR #17 CI (regression + integration level — the full suite on the CI image)
**Verification date:** 2026-07-04
**Verification depth:** functional

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-07-04 | Release gate | CI failed on PR #17; pinned per the local-venv recipe (LL0011: CI-vs-local gap = environment until proven otherwise) |
