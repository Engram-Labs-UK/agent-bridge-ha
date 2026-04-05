"""Response text extraction and helper utilities."""

from __future__ import annotations

from typing import Any

from .const import MAX_TEXT_DEPTH, TEXT_PRIORITY_KEYS


def extract_response_text(data: Any, *, _depth: int = 0) -> str | None:
    """Extract text from a bridge response using priority key traversal.

    Handles varying response structures by checking priority keys at each level
    and recursing into nested dicts/lists up to MAX_TEXT_DEPTH levels.

    Fast path: OpenAI chat completion format (choices[0].message.content).
    """
    if data is None:
        return None

    if isinstance(data, str):
        return data

    if isinstance(data, (int, float, bool)):
        return str(data)

    if _depth >= MAX_TEXT_DEPTH:
        return None

    if isinstance(data, dict):
        # Fast path: OpenAI chat completion format
        if _depth == 0 and "choices" in data:
            choices = data["choices"]
            if isinstance(choices, list) and choices:
                message = choices[0].get("message", {})
                if isinstance(message, dict):
                    content = message.get("content")
                    if content is not None:
                        return str(content) if not isinstance(content, str) else content

        # Priority key check at this level
        for key in TEXT_PRIORITY_KEYS:
            if key in data:
                val = data[key]
                if isinstance(val, str):
                    return val
                if val is not None:
                    result = extract_response_text(val, _depth=_depth + 1)
                    if result is not None:
                        return result

        # Recurse into all dict values
        for val in data.values():
            if isinstance(val, (dict, list)):
                result = extract_response_text(val, _depth=_depth + 1)
                if result is not None:
                    return result

    if isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                result = extract_response_text(item, _depth=_depth + 1)
                if result is not None:
                    return result

    return None


def extract_tool_calls(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract tool_calls from an OpenAI chat completion response."""
    if not isinstance(data, dict):
        return []

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return []

    message = choices[0].get("message", {})
    if not isinstance(message, dict):
        return []

    tool_calls = message.get("tool_calls")
    if isinstance(tool_calls, list):
        return tool_calls

    return []
