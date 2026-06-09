"""DataUpdateCoordinator for Agent Bridge health and discovery polling."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any, NotRequired, TypedDict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .client import BridgeClient, BridgeError
from .const import (
    DEFAULT_DISCOVERY_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    EVENT_AGENT_DISCOVERED,
    EVENT_AGENT_REMOVED,
)
from .helpers import agent_crew

_LOGGER = logging.getLogger(__name__)

# v4.36 /v1/health tri-state `bridge` field -> sensor state (US0028/AC4). The
# middle state surfaces a healthy-but-degraded bridge as a distinct `warning`.
_TRISTATE_MAP = {
    "ready": "ok",
    "ok": "ok",
    "healthy": "ok",
    "warning": "warning",
    "degraded": "warning",
    "error": "error",
    "unavailable": "error",
}


def _map_tristate(value: Any, fallback: str) -> str:
    """Map the /v1/health tri-state `bridge` field to a sensor state."""
    if not isinstance(value, str):
        return fallback
    return _TRISTATE_MAP.get(value.lower(), fallback)


class AgentInfo(TypedDict):
    """Typed agent information from bridge discovery (v4.36 surface, US0028)."""

    id: str
    name: str
    description: str
    healthy: bool
    adapter: str
    capabilities: dict[str, Any]
    tags: list[str]
    # CR-0097 health block
    health_state: str
    circuit: str
    inflight: int
    last_seen_at: str
    stale_after: int
    # CR-0245 metrics
    latency_ms: float
    requests: int
    errors: int
    # CR-0256/0247/0259 taxonomy
    agent_class: str
    identity_substrate: str
    capability_envelope: dict[str, Any]
    is_orchestrator: bool
    framework: str
    effective_model: str
    model_provider: str
    deprecated: bool
    crew: str


class CoordinatorData(TypedDict):
    """Typed coordinator data from bridge polling."""

    connected: bool
    bridge_status: str
    bridge_version: str
    bridge_uptime: int
    agent_count_healthy: int
    agent_count_total: int
    agents: list[AgentInfo]
    last_poll: str
    # /v1/health tri-state surface (US0028/AC4); only set on the success path, so the
    # hard-error CoordinatorData omits them -- typed NotRequired and read via .get().
    tool_surface: NotRequired[str]
    read_only_safe: NotRequired[bool]
    # CR-0009 observability, refreshed on the discovery cadence; read via .get().
    usage: NotRequired[dict[str, dict[str, Any]]]  # keyed by agent_id
    doctor: NotRequired[dict[str, Any]]


class AgentBridgeCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """Coordinator for Agent Bridge health and discovery polling."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: BridgeClient,
        *,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
        discovery_interval: int = DEFAULT_DISCOVERY_INTERVAL,
    ) -> None:
        """Initialise the coordinator."""
        from datetime import timedelta

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=poll_interval),
        )
        self.client = client
        self._discovery_interval = discovery_interval
        self._last_discovery: float = 0
        self._consecutive_failures: int = 0
        self._last_good_data: CoordinatorData | None = None
        self._previous_agents: list[AgentInfo] = []
        # CR-0009: usage (per agent_id) + the fleet doctor verdict, refreshed on the
        # discovery cadence and carried forward between the faster health polls.
        self._usage: dict[str, dict[str, Any]] = {}
        self._doctor: dict[str, Any] = {}

    def _parse_agent(self, raw: dict[str, Any]) -> AgentInfo:
        """Parse a raw agent dict into typed AgentInfo (v4.36 surface, US0028/AC2)."""
        health = raw.get("health") or {}
        metrics = raw.get("metrics") or {}

        # Prefer the richer health.state when present; fall back to legacy status.
        health_state = health.get("state", raw.get("status", "unknown"))
        # A busy/open-circuit/stale agent must read distinctly from healthy: only a
        # ready agent with a closed circuit is "healthy".
        circuit = health.get("circuit", "closed")
        healthy = health_state in ("ready", "healthy") and circuit == "closed"

        return AgentInfo(
            id=raw.get("id", ""),
            name=raw.get("name", raw.get("id", "")),
            description=raw.get("description", ""),
            healthy=healthy,
            adapter=raw.get("adapter", ""),
            capabilities=raw.get("capabilities", {}),
            tags=raw.get("tags", []),
            health_state=health_state,
            circuit=circuit,
            inflight=health.get("inflight", 0),
            last_seen_at=health.get("lastSeenAt", ""),
            stale_after=health.get("staleAfter", 0),
            latency_ms=metrics.get("latency", 0),
            requests=metrics.get("requests", 0),
            errors=metrics.get("errors", 0),
            agent_class=raw.get("agentClass", ""),
            identity_substrate=raw.get("identitySubstrate", ""),
            capability_envelope=raw.get("capabilityEnvelope") or {},
            is_orchestrator=raw.get("isOrchestrator", False),
            framework=raw.get("framework", ""),
            effective_model=raw.get("effectiveModel", ""),
            model_provider=raw.get("modelProvider", ""),
            deprecated=raw.get("deprecated", False),
            crew=agent_crew(raw) or "",
        )

    def _detect_agent_changes(self, new_agents: list[AgentInfo]) -> None:
        """Compare new agent list against previous, fire events for changes."""
        old_ids = {a["id"] for a in self._previous_agents}
        new_ids = {a["id"] for a in new_agents}

        # New agents
        for agent_id in new_ids - old_ids:
            agent = next(a for a in new_agents if a["id"] == agent_id)
            _LOGGER.info("Agent discovered: %s (%s)", agent["name"], agent_id)
            self.hass.bus.async_fire(
                EVENT_AGENT_DISCOVERED,
                {
                    "agent_id": agent_id,
                    "name": agent["name"],
                    "capabilities": agent["capabilities"],
                },
            )

        # Removed agents
        for agent_id in old_ids - new_ids:
            agent = next(a for a in self._previous_agents if a["id"] == agent_id)
            _LOGGER.info("Agent removed: %s (%s)", agent["name"], agent_id)
            self.hass.bus.async_fire(
                EVENT_AGENT_REMOVED,
                {
                    "agent_id": agent_id,
                    "name": agent["name"],
                },
            )

    async def _async_update_data(self) -> CoordinatorData:
        """Poll the bridge for health and discovery data."""
        now = time.monotonic()

        try:
            # Health poll (every cycle)
            health = await self.client.health(depth="shallow")

            # Parse health data
            agents_summary = health.get("agents", {})
            if isinstance(agents_summary, dict):
                total = agents_summary.get("total", 0)
                healthy = agents_summary.get("healthy", 0)
            else:
                total = 0
                healthy = 0

            # Discovery poll (less frequent)
            agents = self._previous_agents
            if now - self._last_discovery >= self._discovery_interval:
                # include=crew so AgentInfo.crew is populated for entity naming (BG0005)
                raw_agents = await self.client.discover(include=["crew"])
                agents = [self._parse_agent(a) for a in raw_agents]
                self._detect_agent_changes(agents)
                self._previous_agents = agents
                self._last_discovery = now
                # CR-0009: refresh usage (per agent) + the fleet doctor on the same
                # slow cadence. Best-effort -- a failure here must not fail the poll.
                await self._refresh_observability(agents)

            # Tri-state /v1/health enrichment (US0028/AC4). Optional + non-fatal: the
            # tri-state `bridge` field maps a healthy-but-warning state distinctly,
            # and toolSurface/readOnlySafe diagnose the actuation gap.
            bridge_status = health.get("status", "unknown")
            tool_surface = ""
            read_only_safe = False
            v1 = await self._poll_v1_health()
            if v1 is not None:
                bridge_status = _map_tristate(v1.get("bridge"), bridge_status)
                tool_surface = v1.get("toolSurface", "")
                read_only_safe = bool(v1.get("readOnlySafe", False))

            data = CoordinatorData(
                connected=True,
                bridge_status=bridge_status,
                bridge_version=health.get("version", "unknown"),
                bridge_uptime=health.get("uptime_seconds", 0),
                agent_count_healthy=healthy,
                agent_count_total=total,
                agents=agents,
                last_poll=datetime.now(tz=UTC).isoformat(),
                tool_surface=tool_surface,
                read_only_safe=read_only_safe,
                usage=self._usage,
                doctor=self._doctor,
            )

            self._consecutive_failures = 0
            self._last_good_data = data
            return data

        except BridgeError as err:
            self._consecutive_failures += 1

            if self._consecutive_failures <= 3 and self._last_good_data is not None:
                _LOGGER.warning(
                    "Bridge poll failed (%d/3), using cached data: %s",
                    self._consecutive_failures,
                    err,
                )
                return CoordinatorData(
                    **{
                        **self._last_good_data,
                        "last_poll": datetime.now(tz=UTC).isoformat(),
                    }
                )

            _LOGGER.error(
                "Bridge unreachable after %d failures: %s",
                self._consecutive_failures,
                err,
            )
            return CoordinatorData(
                connected=False,
                bridge_status="error",
                bridge_version="unknown",
                bridge_uptime=0,
                agent_count_healthy=0,
                agent_count_total=0,
                agents=self._previous_agents,
                last_poll=datetime.now(tz=UTC).isoformat(),
            )

    async def _refresh_observability(self, agents: list[AgentInfo]) -> None:
        """Refresh per-agent usage + the fleet doctor (CR-0009). Best-effort.

        Each call is isolated: one agent's usage failing (or the doctor endpoint
        being unavailable on an older bridge) must not blank the others or fail the
        poll. Values persist between refreshes via ``self._usage``/``self._doctor``.
        """
        usage_fn = getattr(self.client, "agent_usage", None)
        if usage_fn is not None:
            fresh: dict[str, dict[str, Any]] = {}
            for agent in agents:
                agent_id = agent["id"]
                try:
                    result = await usage_fn(agent_id)
                except Exception:
                    # keep the last known value for this agent if we have one
                    if agent_id in self._usage:
                        fresh[agent_id] = self._usage[agent_id]
                    continue
                if isinstance(result, dict):
                    fresh[agent_id] = result
            self._usage = fresh

        doctor_fn = getattr(self.client, "doctor", None)
        if doctor_fn is not None:
            try:
                result = await doctor_fn()
            except Exception:
                result = None
            if isinstance(result, dict):
                self._doctor = result

    async def _poll_v1_health(self) -> dict[str, Any] | None:
        """Poll the auth-gated /v1/health, or None if unavailable (US0028/AC4).

        Non-fatal: a bridge that does not yet serve /v1/health, or a client that
        does not implement it, leaves the shallow-health values in place.
        """
        agent_health = getattr(self.client, "agent_health", None)
        if agent_health is None:
            return None
        try:
            result = await agent_health()
        except Exception:
            return None
        return result if isinstance(result, dict) else None

    async def async_push_webhook_data(self, data: dict[str, Any]) -> None:
        """Accept pushed data from a webhook event, bypassing the poll cycle.

        Two distinct shapes (US0024/G11) -- keep bridge-level status and per-agent
        health separate rather than conflating them:

        * ``{"status": <bridge-status>}`` -- bridge-level status push.
        * ``{"agentId": <id>, "healthy": <bool>}`` -- per-agent health-changed push;
          updates that agent's ``healthy`` flag and recomputes the healthy count.
        """
        if not self.data:
            return

        # Bridge-level status push.
        if "status" in data:
            updated = CoordinatorData(**{**self.data, "bridge_status": data["status"]})
            self.async_set_updated_data(updated)
            return

        # Per-agent health-changed push: {"agentId": ..., "healthy": bool}.
        agent_id = data.get("agentId", data.get("agent_id"))
        if agent_id is not None and "healthy" in data:
            healthy_flag = bool(data["healthy"])
            known_ids = {a["id"] for a in self.data["agents"]}
            if agent_id not in known_ids:
                # Unknown agent -- don't no-op; pull a fresh poll instead.
                await self.async_request_refresh()
                return
            agents = [
                AgentInfo(**{**a, "healthy": healthy_flag}) if a["id"] == agent_id else a
                for a in self.data["agents"]
            ]
            healthy_count = sum(1 for a in agents if a["healthy"])
            updated = CoordinatorData(
                **{
                    **self.data,
                    "agents": agents,
                    "agent_count_healthy": healthy_count,
                }
            )
            self.async_set_updated_data(updated)
