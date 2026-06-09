"""Bridge/HA drift defences -- convert silent drift into operator-visible signal.

US0029 (G13): the component drifted v3.1->v4.36 unnoticed because it never read the
bridge's machine-readable changelog. This fetches ``/v1/agent-context`` (on setup and
on every ``bridge:upgraded`` webhook) and raises an HA repair issue when the live
bridge version moves past the tested baseline or reports deprecations.
"""

from __future__ import annotations

import logging

from awesomeversion import AwesomeVersion, AwesomeVersionException
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .client import BridgeError
from .const import DOMAIN, TESTED_BRIDGE_VERSION

_LOGGER = logging.getLogger(__name__)


def _issue_id(entry: ConfigEntry) -> str:
    return f"bridge_drift_{entry.entry_id}"


def _doctor_issue_id(entry: ConfigEntry) -> str:
    return f"fleet_doctor_{entry.entry_id}"


# Fleet-doctor verdict -> HA repair severity (CR-0009). Only CRITICAL raises a
# persistent repair issue (the home's agents genuinely cannot function). WARNING is
# advisory (e.g. an idle/quiet fleet) -- it stays in the diagnostics download + the
# doctor coordinator data, not a repair notification (BG0011). HEALTHY/unknown: none.
_VERDICT_SEVERITY = {
    "CRITICAL": ir.IssueSeverity.ERROR,
}

_UNSET = object()  # first-call sentinel for the verdict gate (BG0007)


@callback
def async_check_doctor_verdict(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Raise/clear a repair issue from the coordinator's fleet-doctor verdict (CR-0009).

    Reads the doctor payload already cached on the coordinator (no I/O), so this is a
    cheap synchronous listener fired on each coordinator update.
    """
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    coordinator = data.get("coordinator")
    doctor = (coordinator.data or {}).get("doctor", {}) if coordinator else {}

    verdict = str(doctor.get("verdict", "")).upper()
    severity = _VERDICT_SEVERITY.get(verdict)

    # The listener fires every poll but the verdict only refreshes every discovery
    # cycle; only touch the issue registry when the applied state changes (BG0007).
    # A first-call sentinel reconciles any issue left over from a prior session.
    applied = verdict if severity is not None else ""
    prev = getattr(coordinator, "_fleet_doctor_applied", _UNSET) if coordinator else _UNSET
    if prev is not _UNSET and prev == applied:
        return
    if coordinator is not None:
        coordinator._fleet_doctor_applied = applied

    if severity is None:
        ir.async_delete_issue(hass, DOMAIN, _doctor_issue_id(entry))
        return

    findings = doctor.get("findings") or []
    summary = (
        "; ".join(
            f"{f.get('area')}: {f.get('detail')}" for f in findings[:5] if isinstance(f, dict)
        )
        or "see the bridge doctor for detail"
    )
    ir.async_create_issue(
        hass,
        DOMAIN,
        _doctor_issue_id(entry),
        is_fixable=False,
        severity=severity,
        translation_key="fleet_doctor",
        translation_placeholders={"verdict": verdict, "findings": summary},
    )


def _is_newer(live: str, baseline: str) -> bool:
    """Return True if ``live`` is a newer version than ``baseline``."""
    try:
        return AwesomeVersion(live) > AwesomeVersion(baseline)
    except (AwesomeVersionException, ValueError):
        # Unparseable version string -> treat a non-equal value as drift.
        return bool(live) and live != baseline


async def async_check_agent_context_drift(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Fetch /v1/agent-context and raise/clear an HA repair issue on drift.

    Returns True when drift was detected (an issue is raised), else False.
    """
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    client = data.get("client")
    if client is None:
        return False

    try:
        context = await client.agent_context()
    except BridgeError as err:
        _LOGGER.debug("agent-context drift check skipped (%s)", err)
        return False

    live_version = context.get("version", "")
    deprecations = context.get("deprecations") or []

    reasons: list[str] = []
    if live_version and _is_newer(live_version, TESTED_BRIDGE_VERSION):
        reasons.append(f"bridge {live_version} is newer than the tested {TESTED_BRIDGE_VERSION}")
    if deprecations:
        reasons.append(f"{len(deprecations)} deprecation(s) reported")

    if not reasons:
        ir.async_delete_issue(hass, DOMAIN, _issue_id(entry))
        return False

    _LOGGER.warning("Bridge drift detected: %s", "; ".join(reasons))
    ir.async_create_issue(
        hass,
        DOMAIN,
        _issue_id(entry),
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="bridge_drift",
        translation_placeholders={
            "live_version": live_version or "unknown",
            "tested_version": TESTED_BRIDGE_VERSION,
            "reasons": "; ".join(reasons),
        },
    )
    return True
