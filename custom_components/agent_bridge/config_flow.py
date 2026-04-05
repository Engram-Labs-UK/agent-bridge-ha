"""Config flow for Agent Bridge integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import BridgeAuthError, BridgeClient, BridgeConnectionError, BridgeError
from .const import (
    CONF_BRIDGE_TOKEN,
    CONF_BRIDGE_URL,
    CONF_CONTEXT_MAX_CHARS,
    CONF_CONTEXT_STRATEGY,
    CONF_DEBUG_LOGGING,
    CONF_DEFAULT_AGENT,
    CONF_ENABLE_TOOL_CALLS,
    CONF_SSL_VERIFY,
    CONF_THINKING_TIMEOUT,
    CONF_VOICE_AGENT,
    DEFAULT_BRIDGE_URL,
    DEFAULT_CONTEXT_MAX_CHARS,
    DEFAULT_CONTEXT_STRATEGY,
    DEFAULT_THINKING_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BRIDGE_URL, default=DEFAULT_BRIDGE_URL): str,
        vol.Required(CONF_BRIDGE_TOKEN): str,
    }
)


class AgentBridgeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Agent Bridge."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise the config flow."""
        self._bridge_url: str = ""
        self._bridge_token: str = ""
        self._agents: list[dict[str, Any]] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Step 1: Bridge URL and token."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_BRIDGE_URL].rstrip("/")
            token = user_input[CONF_BRIDGE_TOKEN]

            session = async_get_clientsession(self.hass)
            client = BridgeClient(session, url, token, timeout=10, ssl_verify=True)

            try:
                alive = await client.check_alive()
                if not alive:
                    errors["base"] = "cannot_connect"
                else:
                    self._agents = await client.discover()
                    if not self._agents:
                        errors["base"] = "no_agents"
                    else:
                        self._bridge_url = url
                        self._bridge_token = token
                        return await self.async_step_agents()
            except BridgeAuthError:
                errors["base"] = "invalid_auth"
            except BridgeConnectionError:
                errors["base"] = "cannot_connect"
            except BridgeError:
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_agents(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Step 2: Select the agent for voice and chat."""
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

            agent = user_input[CONF_DEFAULT_AGENT]
            return self.async_create_entry(
                title="Agent Bridge",
                data={
                    CONF_BRIDGE_URL: self._bridge_url,
                    CONF_BRIDGE_TOKEN: self._bridge_token,
                    CONF_DEFAULT_AGENT: agent,
                    CONF_VOICE_AGENT: agent,
                },
                options={
                    CONF_CONTEXT_MAX_CHARS: DEFAULT_CONTEXT_MAX_CHARS,
                    CONF_CONTEXT_STRATEGY: DEFAULT_CONTEXT_STRATEGY,
                    CONF_ENABLE_TOOL_CALLS: True,
                    CONF_THINKING_TIMEOUT: DEFAULT_THINKING_TIMEOUT,
                    CONF_SSL_VERIFY: True,
                    CONF_DEBUG_LOGGING: False,
                },
            )

        agent_options = {
            agent["id"]: f"{agent.get('name', agent['id'])} ({agent.get('status', 'unknown')})"
            for agent in self._agents
        }

        return self.async_show_form(
            step_id="agents",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEFAULT_AGENT): vol.In(agent_options),
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> AgentBridgeOptionsFlow:
        """Get the options flow handler."""
        return AgentBridgeOptionsFlow(config_entry)


class AgentBridgeOptionsFlow(OptionsFlow):
    """Handle options for Agent Bridge."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialise options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            # Agent selection lives in entry.data, not options.
            # Extract it and update data separately.
            new_agent = user_input.pop(CONF_DEFAULT_AGENT, None)
            if new_agent:
                new_data = {**self._config_entry.data}
                new_data[CONF_DEFAULT_AGENT] = new_agent
                new_data[CONF_VOICE_AGENT] = new_agent
                self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)

            return self.async_create_entry(title="", data=user_input)

        # Discover current agents from bridge for the dropdown
        agent_options = await self._get_agent_options()

        options = self._config_entry.options
        current_agent = self._config_entry.data.get(CONF_DEFAULT_AGENT, "")

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DEFAULT_AGENT,
                        default=current_agent,
                    ): vol.In(agent_options) if agent_options else str,
                    vol.Optional(
                        CONF_CONTEXT_MAX_CHARS,
                        default=options.get(CONF_CONTEXT_MAX_CHARS, DEFAULT_CONTEXT_MAX_CHARS),
                    ): vol.All(int, vol.Range(min=1000, max=200000)),
                    vol.Optional(
                        CONF_CONTEXT_STRATEGY,
                        default=options.get(CONF_CONTEXT_STRATEGY, DEFAULT_CONTEXT_STRATEGY),
                    ): vol.In(["truncate", "clear"]),
                    vol.Optional(
                        CONF_ENABLE_TOOL_CALLS,
                        default=options.get(CONF_ENABLE_TOOL_CALLS, True),
                    ): bool,
                    vol.Optional(
                        CONF_THINKING_TIMEOUT,
                        default=options.get(CONF_THINKING_TIMEOUT, DEFAULT_THINKING_TIMEOUT),
                    ): vol.All(int, vol.Range(min=10, max=3600)),
                    vol.Optional(
                        CONF_SSL_VERIFY,
                        default=options.get(CONF_SSL_VERIFY, True),
                    ): bool,
                    vol.Optional(
                        CONF_DEBUG_LOGGING,
                        default=options.get(CONF_DEBUG_LOGGING, False),
                    ): bool,
                }
            ),
        )

    async def _get_agent_options(self) -> dict[str, str]:
        """Discover agents from bridge for the options dropdown."""
        try:
            session = async_get_clientsession(self.hass)
            client = BridgeClient(
                session,
                self._config_entry.data[CONF_BRIDGE_URL],
                self._config_entry.data[CONF_BRIDGE_TOKEN],
                timeout=10,
                ssl_verify=self._config_entry.options.get(CONF_SSL_VERIFY, True),
            )
            agents = await client.discover()
            return {
                a["id"]: f"{a.get('name', a['id'])} ({a.get('status', 'unknown')})" for a in agents
            }
        except Exception:
            _LOGGER.warning("Could not discover agents for options flow")
            # Fall back to just the current agent
            current = self._config_entry.data.get(CONF_DEFAULT_AGENT, "")
            return {current: current} if current else {}
