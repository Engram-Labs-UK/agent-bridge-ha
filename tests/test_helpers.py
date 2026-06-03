"""Tests for helpers module -- response text extraction and tool call extraction."""

from types import SimpleNamespace

from custom_components.agent_bridge.const import (
    CONF_CALLER_ID,
    CONF_DEFAULT_AGENT,
    DEFAULT_CALLER_ID,
)
from custom_components.agent_bridge.helpers import (
    extract_response_text,
    extract_tool_calls,
    resolve_caller_id,
)


def _entry(*, options=None, data=None):
    return SimpleNamespace(options=options or {}, data=data or {})


class TestResolveCallerId:
    """BG0004: effective x-bridge-mcp-caller must be a registered agent id."""

    def test_explicit_option_wins(self):
        entry = _entry(
            options={CONF_CALLER_ID: "dbee"},
            data={CONF_DEFAULT_AGENT: "openclaw-openclaw-cora"},
        )
        assert resolve_caller_id(entry) == "dbee"

    def test_falls_back_to_default_agent(self):
        entry = _entry(data={CONF_DEFAULT_AGENT: "openclaw-openclaw-cora"})
        assert resolve_caller_id(entry) == "openclaw-openclaw-cora"

    def test_blank_option_falls_back_to_default_agent(self):
        entry = _entry(
            options={CONF_CALLER_ID: "   "},
            data={CONF_DEFAULT_AGENT: "openclaw-openclaw-cora"},
        )
        assert resolve_caller_id(entry) == "openclaw-openclaw-cora"

    def test_last_resort_default(self):
        assert resolve_caller_id(_entry()) == DEFAULT_CALLER_ID
        # crucially, the legacy literal is never silently used when an agent is set
        assert resolve_caller_id(_entry()) == "homeassistant"


class TestExtractResponseText:
    """Tests for extract_response_text."""

    def test_openai_chat_completion_format(self):
        data = {
            "choices": [{"message": {"role": "assistant", "content": "Hello"}}]
        }
        assert extract_response_text(data) == "Hello"

    def test_string_input(self):
        assert extract_response_text("direct text") == "direct text"

    def test_none_input(self):
        assert extract_response_text(None) is None

    def test_int_input(self):
        assert extract_response_text(42) == "42"

    def test_bool_input(self):
        assert extract_response_text(True) == "True"

    def test_priority_key_text(self):
        assert extract_response_text({"text": "found it"}) == "found it"

    def test_priority_key_content(self):
        assert extract_response_text({"content": "found it"}) == "found it"

    def test_priority_key_message(self):
        assert extract_response_text({"message": "found it"}) == "found it"

    def test_priority_key_output_text(self):
        assert extract_response_text({"output_text": "found it"}) == "found it"

    def test_priority_order(self):
        data = {"content": "second", "text": "first"}
        assert extract_response_text(data) == "first"

    def test_nested_dict(self):
        data = {"data": {"result": {"content": "nested"}}}
        assert extract_response_text(data) == "nested"

    def test_nested_list(self):
        data = {"results": [{"text": "in list"}]}
        assert extract_response_text(data) == "in list"

    def test_depth_limit(self):
        # Build a structure deeper than MAX_TEXT_DEPTH (8)
        data: dict = {"content": "deep"}
        for _ in range(10):
            data = {"nested": data}
        assert extract_response_text(data) is None

    def test_empty_dict(self):
        assert extract_response_text({}) is None

    def test_empty_list(self):
        assert extract_response_text([]) is None

    def test_content_none_in_message(self):
        data = {"choices": [{"message": {"role": "assistant", "content": None}}]}
        assert extract_response_text(data) is None

    def test_empty_choices(self):
        data = {"choices": []}
        assert extract_response_text(data) is None


class TestExtractToolCalls:
    """Tests for extract_tool_calls."""

    def test_standard_tool_calls(self):
        data = {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {"id": "call_1", "function": {"name": "test"}}
                        ]
                    }
                }
            ]
        }
        result = extract_tool_calls(data)
        assert len(result) == 1
        assert result[0]["id"] == "call_1"

    def test_no_tool_calls(self):
        data = {"choices": [{"message": {"content": "Hello"}}]}
        assert extract_tool_calls(data) == []

    def test_empty_choices(self):
        assert extract_tool_calls({"choices": []}) == []

    def test_not_a_dict(self):
        assert extract_tool_calls("not a dict") == []

    def test_no_choices_key(self):
        assert extract_tool_calls({"other": "data"}) == []

    def test_message_not_dict(self):
        data = {"choices": [{"message": "string"}]}
        assert extract_tool_calls(data) == []

    def test_tool_calls_not_list(self):
        data = {"choices": [{"message": {"tool_calls": "not a list"}}]}
        assert extract_tool_calls(data) == []
