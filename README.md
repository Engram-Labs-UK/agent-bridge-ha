# Agent Bridge HA

[![Validate](https://github.com/Engram-Labs-UK/agent-bridge-ha/actions/workflows/validate.yml/badge.svg)](https://github.com/Engram-Labs-UK/agent-bridge-ha/actions/workflows/validate.yml)

Home Assistant custom component that connects [Agent Bridge](https://github.com/Engram-Labs-UK/agent-bridge) agents to Home Assistant's conversation, voice, and automation frameworks.

Agents appear as native HA conversation agents with full entity exposure, room awareness, health monitoring, tool execution, and automation events.

## Features

- **Conversation agents** -- each bridge agent selectable in HA Assist pipelines (voice satellites, text chat)
- **Entity exposure** -- formats HA entity state (names, areas, attributes) for AI context
- **Room awareness** -- injects device area into prompts so "turn on the lights" means *this room's* lights
- **Tool execution** -- agents control the home via `tool_calls` (lights, climate, locks, media)
- **Health monitoring** -- sensors for bridge status, connectivity, agent count, per-agent health
- **Automation events** -- `message_received` and `tool_invoked` events for HA automations
- **Services** -- `send_message`, `invoke_tool`, `broadcast` for automation builders
- **Session persistence** -- conversation context survives HA restarts
- **SSE streaming** -- lower-latency voice responses via Server-Sent Events
- **Webhook integration** -- real-time health updates from the bridge

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. Three-dot menu > **Custom repositories**
3. Add `Engram-Labs-UK/agent-bridge-ha` as **Integration**
4. Search "Agent Bridge" in HACS, install
5. Restart HA

### Manual

Copy `custom_components/agent_bridge/` to your HA `config/custom_components/` directory and restart.

## Setup

1. **Settings > Devices & Services > Add Integration > Agent Bridge**
2. Enter bridge URL (e.g. `http://10.0.0.206:18780`) and API token
3. Select default chat agent and voice agent from discovered agents
4. Done -- sensors, conversation agent, and events are created

## Configuration

Post-setup options available in **Settings > Devices & Services > Agent Bridge > Configure**:

| Option | Default | Description |
|--------|---------|-------------|
| Context max chars | 13000 | Max entity context in AI prompt |
| Context strategy | truncate | `truncate` or `clear` on overflow |
| Per-agent entities | off | Separate conversation agent per bridge agent |
| Tool calls | on | Allow agents to control HA devices |
| Thinking timeout | 120s | Agent response timeout |
| SSL verify | on | Verify bridge SSL certificates |
| Debug logging | off | Log voice routing decisions |

## Requirements

- Home Assistant 2025.2.0+ (tested against 2026.2.3; modern `ConversationEntity` +
  `ChatLog` + config subentries require 2025.2+)
- Agent Bridge instance v4.36.0+ (the tested baseline; the v3.1-era contract has drifted)
- Valid bridge API token

## Development

```bash
python -m pytest tests/ -v          # Run tests
ruff check custom_components/       # Lint
ruff format custom_components/      # Format
```

## Licence

MIT -- see [LICENCE](LICENCE).
