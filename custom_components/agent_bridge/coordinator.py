"""DataUpdateCoordinator for Agent Bridge health and discovery polling."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, TypedDict

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

_LOGGER = logging.getLogger(__name__)


class AgentInfo(TypedDict):
    """Typed agent information from bridge discovery."""

    id: str
    name: str
    description: str
    healthy: bool
    adapter: str
    capabilities: dict[str, Any]
    tags: list[str]


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

    def _parse_agent(self, raw: dict[str, Any]) -> AgentInfo:
        """Parse a raw agent dict into typed AgentInfo."""
        return AgentInfo(
            id=raw.get("id", ""),
            name=raw.get("name", raw.get("id", "")),
            description=raw.get("description", ""),
            healthy=raw.get("status") == "healthy",
            adapter=raw.get("adapter", ""),
            capabilities=raw.get("capabilities", {}),
            tags=raw.get("tags", []),
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
        import time

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
                raw_agents = await self.client.discover()
                agents = [self._parse_agent(a) for a in raw_agents]
                self._detect_agent_changes(agents)
                self._previous_agents = agents
                self._last_discovery = now

            data = CoordinatorData(
                connected=True,
                bridge_status=health.get("status", "unknown"),
                bridge_version=health.get("version", "unknown"),
                bridge_uptime=health.get("uptime_seconds", 0),
                agent_count_healthy=healthy,
                agent_count_total=total,
                agents=agents,
                last_poll=datetime.now(tz=UTC).isoformat(),
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
