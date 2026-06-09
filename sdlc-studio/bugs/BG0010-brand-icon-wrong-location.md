<!--
Template: Bug Report (Streamlined)
File: sdlc-studio/bugs/BG{NNNN}-{slug}.md
Status values: See reference-outputs.md
Related: help/bug.md, reference-bug.md
-->
# BG0010: Brand icon in the wrong location — "icon not available" in the integrations dashboard

> **Status:** Fixed
> **Severity:** Low
> **Priority:** P3
> **Reporter:** Darren Benson
> **Assignee:** —
> **Created:** 2026-06-09
> **Verification depth:** functional

## Summary

The integrations dashboard shows "icon not available" for Agent Bridge. CR-0005 placed the brand assets at `custom_components/agent_bridge/icon.png` and `custom_components/agent_bridge/icons/icon.png`, but Home Assistant (2026.3+) serves custom-integration brand images **only from a `brand/` subdirectory** (`custom_components/agent_bridge/brand/icon.png`). The root copy is ignored; `icons/` is for entity icons (`icons.json`), not brand images. So HA finds no brand icon and falls back to the CDN, which has no entry for this custom domain → "icon not available".

**Verify:** `custom_components/agent_bridge/brand/icon.png` exists (256x256) with `icon@2x.png`/`logo.png`/`logo@2x.png`, and no stray `icon.png` remains at the integration root or under `icons/`.

## Affected Area

- **Component:** brand assets
- **Origin:** CR-0005 (wrong location)

## Environment

- **Version:** 0.10.1 (fix ships in 0.10.2); live HA 2026.6.1

---

## Reproduction Steps

1. Install the integration; open Settings → Devices & Services → Agent Bridge.
2. The header shows a grey "icon not available" box instead of the Agent Crew logo.

## Expected Behaviour

The Agent Crew brand icon appears (HA serves `brand/icon.png` locally, taking precedence over the CDN).

## Actual Behaviour

"icon not available" — the brand assets were in the root + `icons/`, neither of which HA reads for branding.

---

## Root Cause Analysis

HA 2026.3 introduced local brand images for custom integrations, served from a `brand/` subdirectory (developers.home-assistant blog, 2026-02-24). CR-0005 predated/ignored that and used the integration root + `icons/`.

## Fix Description

Created `custom_components/agent_bridge/brand/` with `icon.png` (256), `icon@2x.png` (512), `logo.png`, `logo@2x.png` from the Agent Crew source. Removed the misplaced `icon.png`/`icon@2x.png` from the integration root and the `icons/` copies (`icons/` is for `icons.json` entity icons only).

### Files Modified

| File | Change |
|------|--------|
| `brand/icon.png`, `brand/icon@2x.png`, `brand/logo.png`, `brand/logo@2x.png` | New (correct location) |
| `icon.png`, `icon@2x.png`, `icons/icon.png`, `icons/icon@2x.png` | Removed (wrong location) |

---

## Verification

- [x] Fix verified in development (assets in `brand/`; misplaced copies gone)
- [ ] Live: dashboard shows the icon after update + restart + browser hard-refresh (HA/CDN brand cache can lag)

**Verified by:** structure check; live confirmation pending the 0.10.2 update + reload
**Verification date:** 2026-06-09
**Verification depth:** functional

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-06-09 | Darren Benson | Reported ("icon not available" on the live 0.10.0 install); root-caused to the `brand/` location requirement |
