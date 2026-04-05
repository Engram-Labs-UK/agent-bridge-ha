"""Tests for SSE streaming in bridge client and conversation agent."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.agent_bridge.client import (
    BridgeClient,
    BridgeAuthError,
    BridgeConnectionError,
    BridgeTimeoutError,
)
from custom_components.agent_bridge.conversation import _stream_chat


class MockSSEResponse:
    """Mock aiohttp response that yields SSE lines."""

    def __init__(self, chunks: list[str], status: int = 200):
        self.status = status
        self.content = self._make_content(chunks)
        self._closed = False

    def _make_content(self, chunks):
        class _Content:
            def __init__(self, data):
                self._data = data
            async def __aiter__(self_inner):
                for chunk in self_inner._data:
                    yield chunk.encode("utf-8")
        return _Content(chunks)

    def close(self):
        self._closed = True


def _sse_line(content_text: str) -> str:
    """Build an SSE data line with OpenAI delta format."""
    chunk = {"choices": [{"delta": {"content": content_text}}]}
    return f"data: {json.dumps(chunk)}\n"


class TestChatStream:

    @pytest.mark.asyncio
    async def test_yields_content_deltas(self):
        session = MagicMock(spec=aiohttp.ClientSession)
        client = BridgeClient(session, "http://bridge:18780", "tok")

        sse_resp = MockSSEResponse([
            _sse_line("Hello"),
            _sse_line(" world"),
            "data: [DONE]\n",
        ])
        session.request = AsyncMock(return_value=sse_resp)

        parts = []
        async for delta in await client.chat_stream(
            [{"role": "user", "content": "Hi"}], agent="cora"
        ):
            parts.append(delta)

        assert parts == ["Hello", " world"]

    @pytest.mark.asyncio
    async def test_stops_on_done(self):
        session = MagicMock(spec=aiohttp.ClientSession)
        client = BridgeClient(session, "http://bridge:18780", "tok")

        sse_resp = MockSSEResponse([
            _sse_line("text"),
            "data: [DONE]\n",
            _sse_line("should not appear"),
        ])
        session.request = AsyncMock(return_value=sse_resp)

        parts = []
        async for delta in await client.chat_stream(
            [{"role": "user", "content": "Hi"}]
        ):
            parts.append(delta)

        assert parts == ["text"]

    @pytest.mark.asyncio
    async def test_skips_empty_lines(self):
        session = MagicMock(spec=aiohttp.ClientSession)
        client = BridgeClient(session, "http://bridge:18780", "tok")

        sse_resp = MockSSEResponse([
            "\n",
            ":\n",  # SSE comment
            _sse_line("content"),
            "data: [DONE]\n",
        ])
        session.request = AsyncMock(return_value=sse_resp)

        parts = []
        async for delta in await client.chat_stream(
            [{"role": "user", "content": "Hi"}]
        ):
            parts.append(delta)

        assert parts == ["content"]

    @pytest.mark.asyncio
    async def test_skips_chunks_without_content(self):
        session = MagicMock(spec=aiohttp.ClientSession)
        client = BridgeClient(session, "http://bridge:18780", "tok")

        no_content_chunk = json.dumps({"choices": [{"delta": {}}]})
        sse_resp = MockSSEResponse([
            f"data: {no_content_chunk}\n",
            _sse_line("actual"),
            "data: [DONE]\n",
        ])
        session.request = AsyncMock(return_value=sse_resp)

        parts = []
        async for delta in await client.chat_stream(
            [{"role": "user", "content": "Hi"}]
        ):
            parts.append(delta)

        assert parts == ["actual"]

    @pytest.mark.asyncio
    async def test_skips_invalid_json(self):
        session = MagicMock(spec=aiohttp.ClientSession)
        client = BridgeClient(session, "http://bridge:18780", "tok")

        sse_resp = MockSSEResponse([
            "data: not json\n",
            _sse_line("valid"),
            "data: [DONE]\n",
        ])
        session.request = AsyncMock(return_value=sse_resp)

        parts = []
        async for delta in await client.chat_stream(
            [{"role": "user", "content": "Hi"}]
        ):
            parts.append(delta)

        assert parts == ["valid"]

    @pytest.mark.asyncio
    async def test_auth_error(self):
        session = MagicMock(spec=aiohttp.ClientSession)
        client = BridgeClient(session, "http://bridge:18780", "tok")

        resp = MagicMock()
        resp.status = 401
        resp.close = MagicMock()
        session.request = AsyncMock(return_value=resp)

        with pytest.raises(BridgeAuthError):
            await client.chat_stream([{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_connection_error(self):
        session = MagicMock(spec=aiohttp.ClientSession)
        client = BridgeClient(session, "http://bridge:18780", "tok")

        session.request = AsyncMock(side_effect=aiohttp.ClientError("refused"))

        with pytest.raises(BridgeConnectionError):
            await client.chat_stream([{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_timeout_error(self):
        session = MagicMock(spec=aiohttp.ClientSession)
        client = BridgeClient(session, "http://bridge:18780", "tok")

        session.request = AsyncMock(side_effect=asyncio.TimeoutError())

        with pytest.raises(BridgeTimeoutError):
            await client.chat_stream([{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_sends_stream_true(self):
        session = MagicMock(spec=aiohttp.ClientSession)
        client = BridgeClient(session, "http://bridge:18780", "tok")

        sse_resp = MockSSEResponse(["data: [DONE]\n"])
        session.request = AsyncMock(return_value=sse_resp)

        async for _ in await client.chat_stream(
            [{"role": "user", "content": "Hi"}],
            agent="cora",
            channel="session-1",
        ):
            pass

        call_args = session.request.call_args
        body = call_args.kwargs.get("json") or call_args[1].get("json")
        assert body["stream"] is True
        assert body["agent"] == "cora"
        assert body["channel"] == "session-1"

    @pytest.mark.asyncio
    async def test_response_closed(self):
        session = MagicMock(spec=aiohttp.ClientSession)
        client = BridgeClient(session, "http://bridge:18780", "tok")

        sse_resp = MockSSEResponse([
            _sse_line("text"),
            "data: [DONE]\n",
        ])
        session.request = AsyncMock(return_value=sse_resp)

        async for _ in await client.chat_stream(
            [{"role": "user", "content": "Hi"}]
        ):
            pass

        assert sse_resp._closed


class TestStreamChat:
    """Tests for the _stream_chat helper in conversation.py."""

    @pytest.mark.asyncio
    async def test_assembles_deltas(self):
        client = MagicMock()

        async def mock_stream(*args, **kwargs):
            async def gen():
                yield "Hello"
                yield " world"
            return gen()

        client.chat_stream = mock_stream

        result = await _stream_chat(
            client, [{"role": "user", "content": "Hi"}], agent="cora"
        )
        assert result == "Hello world"

    @pytest.mark.asyncio
    async def test_returns_none_for_empty_stream(self):
        client = MagicMock()

        async def mock_stream(*args, **kwargs):
            async def gen():
                return
                yield  # make it an async generator
            return gen()

        client.chat_stream = mock_stream

        result = await _stream_chat(
            client, [{"role": "user", "content": "Hi"}]
        )
        assert result is None
