"""Config flow for Agent Bridge integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult, section
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

from .client import BridgeAuthError, BridgeClient, BridgeConnectionError, BridgeError
from .const import (
    CONF_AGENT_ID,
    CONF_BRIDGE_TOKEN,
    CONF_BRIDGE_URL,
    CONF_CONTEXT_MAX_CHARS,
    CONF_CREW,
    CONF_DEFAULT_AGENT,
    CONF_DOCTOR_ALERTS,
    CONF_ENABLE_STREAMING,
    CONF_PROMPT,
    CONF_SESSION_IDLE_WINDOW,
    CONF_SSL_VERIFY,
    CONF_THINKING_TIMEOUT,
    CONF_VOICE_AGENT,
    DEFAULT_BRIDGE_URL,
    DEFAULT_CONTEXT_MAX_CHARS,
    DEFAULT_ENABLE_STREAMING,
    DEFAULT_PROMPT,
    DEFAULT_SESSION_IDLE_WINDOW,
    DEFAULT_THINKING_TIMEOUT,
    DOMAIN,
    SESSION_IDLE_PRESETS,
    SUBENTRY_TYPE_CONVERSATION,
)
from .helpers import agent_crew, agent_label, is_selectable_agent, resolve_caller_id

ALL_CREWS = "__all__"

# Collapsible "Advanced" section in the options form (CR-0007). Stored options stay
# flat -- the section is flattened back to top level on submit for back-compat.
ADVANCED_SECTION = "advanced"

# CR-0013: friendly labels for the session-continuity preset dropdown.
_SESSION_IDLE_LABELS = {
    0: "Off (no continuity)",
    300: "5 minutes",
    1800: "30 minutes",
    7200: "2 hours",
    28800: "8 hours",
    86400: "24 hours (bridge max)",
}
_SESSION_IDLE_OPTIONS = [
    SelectOptionDict(value=str(s), label=_SESSION_IDLE_LABELS[s]) for s in SESSION_IDLE_PRESETS
]


async def _discover_agents(hass, entry: ConfigEntry) -> list[dict[str, Any]]:
    """Discover raw agents from the bridge (shared by the pickers).

    Requests ``include=crew`` so each agent carries its crew membership
    (``crew.team``) for the crew-scoped picker (CR-0003).
    """
    session = async_get_clientsession(hass)
    client = BridgeClient(
        session,
        entry.data[CONF_BRIDGE_URL],
        entry.data[CONF_BRIDGE_TOKEN],
        timeout=10,
        ssl_verify=entry.options.get(CONF_SSL_VERIFY, True),
        caller_id=resolve_caller_id(entry),
    )
    return await client.discover(include=["crew"])


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
                    # include=crew so the first-run picker shows "name (crew)" like the
                    # options + subentry pickers (BG0009).
                    self._agents = await client.discover(include=["crew"])
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
                    CONF_THINKING_TIMEOUT: DEFAULT_THINKING_TIMEOUT,
                    CONF_SSL_VERIFY: True,
                },
            )

        # Only list real, selectable agents -- not models/chatbots/workerbots (CR-0003).
        agent_options = {
            agent["id"]: agent_label(agent) for agent in self._agents if is_selectable_agent(agent)
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

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Add a bridge agent as a conversation subentry -> one entity (US0025)."""
        return {SUBENTRY_TYPE_CONVERSATION: ConversationSubentryFlowHandler}


def _prompt_schema(default: str) -> vol.Schema:
    """Schema for the editable per-agent instructions field (CR-0003)."""
    return vol.Schema(
        {
            vol.Optional(CONF_PROMPT, default=default): TextSelector(
                TextSelectorConfig(multiline=True)
            ),
        }
    )


class ConversationSubentryFlowHandler(ConfigSubentryFlow):
    """Add a bridge agent as a ConversationEntity: crew -> agent -> instructions.

    CR-0003: a cascading crew picker then a crew-scoped agent picker (real agents
    only -- no models/chatbots/workerbots), plus an editable Instructions field
    (default :data:`DEFAULT_PROMPT`) that the entity folds into the system prompt.
    Editable later via the reconfigure step.
    """

    def __init__(self) -> None:
        self._agents: list[dict[str, Any]] = []
        self._crew: str | None = None

    async def _load_agents(self) -> list[dict[str, Any]]:
        """Discover + cache the selectable agents for this flow."""
        if self._agents:
            return self._agents
        try:
            raw = await _discover_agents(self.hass, self._get_entry())
        except Exception:
            _LOGGER.warning("Could not discover agents for conversation subentry")
            raw = []
        self._agents = [a for a in raw if is_selectable_agent(a)]
        return self._agents

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Step 1: pick a crew (or All crews)."""
        agents = await self._load_agents()
        if not agents:
            return self.async_abort(reason="no_agents")

        crews = sorted({c for a in agents if (c := agent_crew(a))})
        # No crews declared -> skip straight to the agent picker.
        if not crews:
            self._crew = None
            return await self.async_step_agent()

        if user_input is not None:
            self._crew = None if user_input[CONF_CREW] == ALL_CREWS else user_input[CONF_CREW]
            return await self.async_step_agent()

        crew_options = {ALL_CREWS: "All crews", **{c: c for c in crews}}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_CREW, default=ALL_CREWS): vol.In(crew_options)}
            ),
        )

    async def async_step_agent(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Step 2: pick an agent in the chosen crew + set instructions."""
        agents = [a for a in self._agents if self._crew is None or agent_crew(a) == self._crew]
        if not agents:
            return self.async_abort(reason="no_agents")

        if user_input is not None:
            agent_id = user_input[CONF_AGENT_ID]
            chosen = next((a for a in agents if a["id"] == agent_id), {})
            return self.async_create_entry(
                title=chosen.get("name", agent_id),
                data={
                    CONF_AGENT_ID: agent_id,
                    CONF_CREW: agent_crew(chosen),
                    CONF_PROMPT: user_input.get(CONF_PROMPT, DEFAULT_PROMPT),
                },
            )

        agent_options = {a["id"]: agent_label(a) for a in agents}
        schema = vol.Schema({vol.Required(CONF_AGENT_ID): vol.In(agent_options)}).extend(
            _prompt_schema(DEFAULT_PROMPT).schema
        )
        return self.async_show_form(step_id="agent", data_schema=schema)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit an existing agent entity's instructions (CR-0003)."""
        subentry = self._get_reconfigure_subentry()
        current = subentry.data.get(CONF_PROMPT, DEFAULT_PROMPT)

        if user_input is not None:
            return self.async_update_and_abort(
                self._get_entry(),
                subentry,
                data={**subentry.data, CONF_PROMPT: user_input[CONF_PROMPT]},
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_prompt_schema(current),
        )


class AgentBridgeOptionsFlow(OptionsFlow):
    """Handle options for Agent Bridge."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialise options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage the options (CR-0007: essentials + a collapsed Advanced section)."""
        if user_input is not None:
            # Flatten the Advanced section back to the top level so stored options
            # stay flat (back-compat with every entry.options.get(...) reader).
            advanced = user_input.pop(ADVANCED_SECTION, {})
            merged = {**user_input, **advanced}

            # CR-0013: the session-continuity dropdown yields a string; store it as an
            # int so conversation.py keeps reading a number.
            if CONF_SESSION_IDLE_WINDOW in merged:
                try:
                    merged[CONF_SESSION_IDLE_WINDOW] = int(merged[CONF_SESSION_IDLE_WINDOW])
                except (TypeError, ValueError):
                    merged[CONF_SESSION_IDLE_WINDOW] = DEFAULT_SESSION_IDLE_WINDOW

            # Agent selection lives in entry.data, not options.
            new_agent = merged.pop(CONF_DEFAULT_AGENT, None)
            if new_agent:
                new_data = {**self._config_entry.data}
                new_data[CONF_DEFAULT_AGENT] = new_agent
                new_data[CONF_VOICE_AGENT] = new_agent
                self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)

            return self.async_create_entry(title="", data=merged)

        # Discover current agents from bridge for the dropdown
        agent_options = await self._get_agent_options()

        options = self._config_entry.options
        current_agent = self._config_entry.data.get(CONF_DEFAULT_AGENT, "")

        # Essentials: pick the agent + the one transport toggle most installs touch.
        essentials = {
            vol.Required(
                CONF_DEFAULT_AGENT,
                default=current_agent,
            ): vol.In(agent_options) if agent_options else str,
            vol.Optional(
                CONF_SSL_VERIFY,
                default=options.get(CONF_SSL_VERIFY, True),
            ): bool,
        }

        # CR-0013: pre-select the stored session value if it is a known preset, else
        # fall back to the default preset (handles legacy non-preset values).
        stored_session = options.get(CONF_SESSION_IDLE_WINDOW, DEFAULT_SESSION_IDLE_WINDOW)
        session_default = (
            str(stored_session)
            if stored_session in SESSION_IDLE_PRESETS
            else str(DEFAULT_SESSION_IDLE_WINDOW)
        )

        # Advanced: tuning that has sane defaults; collapsed by default.
        advanced_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_CONTEXT_MAX_CHARS,
                    default=options.get(CONF_CONTEXT_MAX_CHARS, DEFAULT_CONTEXT_MAX_CHARS),
                ): vol.All(int, vol.Range(min=1000, max=200000)),
                vol.Optional(
                    CONF_THINKING_TIMEOUT,
                    default=options.get(CONF_THINKING_TIMEOUT, DEFAULT_THINKING_TIMEOUT),
                ): vol.All(int, vol.Range(min=10, max=3600)),
                # US0032/CR-0013: idle gap that rotates the session channel key, as a
                # friendly preset dropdown (Off..24h). Stored as an int (coerced above).
                vol.Optional(
                    CONF_SESSION_IDLE_WINDOW,
                    default=session_default,
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=_SESSION_IDLE_OPTIONS,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                # US0033: opt-in response streaming to TTS (experimental).
                vol.Optional(
                    CONF_ENABLE_STREAMING,
                    default=options.get(CONF_ENABLE_STREAMING, DEFAULT_ENABLE_STREAMING),
                ): bool,
                # CR-0012: opt-in fleet-doctor repair issue (operator diagnostic).
                vol.Optional(
                    CONF_DOCTOR_ALERTS,
                    default=options.get(CONF_DOCTOR_ALERTS, False),
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    **essentials,
                    vol.Required(ADVANCED_SECTION): section(advanced_schema, {"collapsed": True}),
                }
            ),
        )

    async def _get_agent_options(self) -> dict[str, str]:
        """Discover agents from bridge for the options dropdown.

        Uses the shared ``_discover_agents`` helper so the ``x-bridge-mcp-caller``
        header is sent, matching the subentry flow (BG0015 / BG0004 parity), and
        the picker label stays "name (crew)" (BG0009).
        """
        try:
            agents = await _discover_agents(self.hass, self._config_entry)
            # Real, selectable agents only -- not models/chatbots/workerbots (CR-0003).
            return {a["id"]: agent_label(a) for a in agents if is_selectable_agent(a)}
        except Exception:
            _LOGGER.warning("Could not discover agents for options flow")
            # Fall back to just the current agent
            current = self._config_entry.data.get(CONF_DEFAULT_AGENT, "")
            return {current: current} if current else {}
