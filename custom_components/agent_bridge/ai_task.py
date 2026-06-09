"""AI Task platform for Agent Bridge (US0039).

One ``ai_task`` entity per bridge agent: lets automations, dashboards and
templates ask an agent for structured data or a summary via
``ai_task.generate_data``. Deliberately tightly scoped (no image generation, no
schema registry, no approval workflow) per the live-agent consult -- it reuses
the same bridge client as the conversation entity.
"""

from __future__ import annotations

import json
import logging

from homeassistant.components.ai_task import (
    AITaskEntity,
    AITaskEntityFeature,
    GenDataTask,
    GenDataTaskResult,
)
from homeassistant.components.conversation import ChatLog
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .client import BridgeClient, BridgeError
from .const import DOMAIN
from .conversation import (
    _agents_from_entry,
    _is_voice_capable,
    _messages_from_chat_log,
)
from .helpers import agent_label, extract_response_text

_LOGGER = logging.getLogger(__name__)


def _strip_code_fence(text: str) -> str:
    """Strip a leading ```json / ``` fence and trailing ``` from a JSON reply."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else ""
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rstrip()[:-3]
    return stripped.strip()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one AI Task entity per bridge agent (US0039)."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    client: BridgeClient = data["client"]
    coordinator = data.get("coordinator")
    agents_by_id = {}
    if coordinator is not None and coordinator.data:
        agents_by_id = {a["id"]: a for a in coordinator.data["agents"]}

    for agent_id, agent_name, subentry_id, _prompt in _agents_from_entry(config_entry):
        agent_info = agents_by_id.get(agent_id)
        if not _is_voice_capable(agent_info):
            continue
        # BG0005: friendly name from discovery, never the raw agent id.
        display_name = agent_label(agent_info) if agent_info else agent_name
        entity = AgentBridgeAITaskEntity(
            config_entry,
            client,
            agent_id=agent_id,
            agent_name=display_name,
            subentry_id=subentry_id,
        )
        if subentry_id is not None:
            async_add_entities([entity], config_subentry_id=subentry_id)
        else:
            async_add_entities([entity])


class AgentBridgeAITaskEntity(AITaskEntity):
    """An AI Task entity backed by a bridge agent."""

    _attr_has_entity_name = True
    _attr_supported_features = AITaskEntityFeature.GENERATE_DATA

    def __init__(
        self,
        entry: ConfigEntry,
        client: BridgeClient,
        *,
        agent_id: str,
        agent_name: str,
        subentry_id: str | None = None,
    ) -> None:
        """Initialise the AI Task entity for a single bridge agent."""
        self.entry = entry
        self.client = client
        self._agent_id = agent_id
        self._attr_name = agent_name
        unique_suffix = subentry_id or agent_id
        self._attr_unique_id = f"{entry.entry_id}_aitask_{unique_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{unique_suffix}")},
            name=agent_name,
            manufacturer="Agent Bridge",
            model=agent_id,
            entry_type=DeviceEntryType.SERVICE,
        )

    async def _async_generate_data(
        self,
        task: GenDataTask,
        chat_log: ChatLog,
    ) -> GenDataTaskResult:
        """Generate data (free text, or JSON when a structure is requested)."""
        messages = _messages_from_chat_log(chat_log)
        if task.structure is not None:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "Respond with ONLY valid JSON (no prose, no code fence) "
                        "matching the requested structure."
                    ),
                }
            )

        try:
            response = await self.client.chat(messages, agent=self._agent_id)
        except BridgeError as err:
            raise HomeAssistantError(f"Agent request failed: {err}") from err

        text = extract_response_text(response) or ""

        if task.structure is None:
            return GenDataTaskResult(conversation_id=chat_log.conversation_id, data=text)

        try:
            data = json.loads(_strip_code_fence(text))
        except (ValueError, TypeError) as err:
            raise HomeAssistantError(
                f"Agent did not return valid JSON for the requested structure: {err}"
            ) from err
        return GenDataTaskResult(conversation_id=chat_log.conversation_id, data=data)
