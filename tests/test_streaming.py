"""Tests for SSE streaming in bridge client and conversation agent."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.agent_bridge.client import (
    BridgeAuthError,
    BridgeClient,
    BridgeConnectionError,
    BridgeTimeoutError,
)
from custom_components.agent_bridge.conversation import _stream_chat, _to_delta_stream


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


def _v436_message(text: str) -> list[str]:
    """Build a v4.36 message frame: event:message then data:{text}."""
    return ["event:message\n", f"data:{json.dumps({'text': text})}\n", "\n"]


class TestChatStreamV436:
    """US0023/G7: v4.36 SSE shape (event:message {text} + event:done)."""

    @pytest.mark.asyncio
    async def test_yields_text_delta(self):
        session = MagicMock(spec=aiohttp.ClientSession)
        client = BridgeClient(session, "http://bridge:18780", "tok")

        sse_resp = MockSSEResponse(
            [*_v436_message("hi"), *_v436_message(" there"), "event:done\n", "\n"]
        )
        session.request = AsyncMock(return_value=sse_resp)

        parts = [
            d
            async for d in await client.chat_stream(
                [{"role": "user", "content": "Hi"}], agent="cora"
            )
        ]
        assert parts == ["hi", " there"]

    @pytest.mark.asyncio
    async def test_event_done_terminates(self):
        session = MagicMock(spec=aiohttp.ClientSession)
        client = BridgeClient(session, "http://bridge:18780", "tok")

        sse_resp = MockSSEResponse(
            [*_v436_message("first"), "event:done\n", "\n", *_v436_message("after")]
        )
        session.request = AsyncMock(return_value=sse_resp)

        parts = [d async for d in await client.chat_stream([{"role": "user", "content": "Hi"}])]
        assert parts == ["first"]

    @pytest.mark.asyncio
    async def test_socket_close_terminates_without_done(self):
        """No [DONE] sentinel, no event:done -- a bare socket close ends cleanly."""
        session = MagicMock(spec=aiohttp.ClientSession)
        client = BridgeClient(session, "http://bridge:18780", "tok")

        sse_resp = MockSSEResponse([*_v436_message("only")])  # stream just ends
        session.request = AsyncMock(return_value=sse_resp)

        parts = [d async for d in await client.chat_stream([{"role": "user", "content": "Hi"}])]
        assert parts == ["only"]
        assert sse_resp._closed


class TestStreamFailSafe:
    """US0023/AC3: real stream faults propagate (caller logs + falls back), not swallowed.

    ``_stream_chat`` must NOT swallow exceptions -- the caller (async_process)
    owns the log-at-error + fall-back-to-non-streaming behaviour. These tests pin
    that the helper re-raises rather than hiding the fault.
    """

    @pytest.mark.asyncio
    async def test_runtime_error_propagates(self):
        client = MagicMock()

        async def boom_stream(*args, **kwargs):
            raise RuntimeError("stream exploded")

        client.chat_stream = boom_stream
        with pytest.raises(RuntimeError):
            await _stream_chat(client, [{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_cancelled_error_not_swallowed(self):
        client = MagicMock()

        async def cancel_stream(*args, **kwargs):
            raise asyncio.CancelledError()

        client.chat_stream = cancel_stream
        with pytest.raises(asyncio.CancelledError):
            await _stream_chat(client, [{"role": "user", "content": "Hi"}])


class TestChatStream:
    @pytest.mark.asyncio
    async def test_yields_content_deltas(self):
        session = MagicMock(spec=aiohttp.ClientSession)
        client = BridgeClient(session, "http://bridge:18780", "tok")

        sse_resp = MockSSEResponse(
            [
                _sse_line("Hello"),
                _sse_line(" world"),
                "data: [DONE]\n",
            ]
        )
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

        sse_resp = MockSSEResponse(
            [
                _sse_line("text"),
                "data: [DONE]\n",
                _sse_line("should not appear"),
            ]
        )
        session.request = AsyncMock(return_value=sse_resp)

        parts = []
        async for delta in await client.chat_stream([{"role": "user", "content": "Hi"}]):
            parts.append(delta)

        assert parts == ["text"]

    @pytest.mark.asyncio
    async def test_skips_empty_lines(self):
        session = MagicMock(spec=aiohttp.ClientSession)
        client = BridgeClient(session, "http://bridge:18780", "tok")

        sse_resp = MockSSEResponse(
            [
                "\n",
                ":\n",  # SSE comment
                _sse_line("content"),
                "data: [DONE]\n",
            ]
        )
        session.request = AsyncMock(return_value=sse_resp)

        parts = []
        async for delta in await client.chat_stream([{"role": "user", "content": "Hi"}]):
            parts.append(delta)

        assert parts == ["content"]

    @pytest.mark.asyncio
    async def test_skips_chunks_without_content(self):
        session = MagicMock(spec=aiohttp.ClientSession)
        client = BridgeClient(session, "http://bridge:18780", "tok")

        no_content_chunk = json.dumps({"choices": [{"delta": {}}]})
        sse_resp = MockSSEResponse(
            [
                f"data: {no_content_chunk}\n",
                _sse_line("actual"),
                "data: [DONE]\n",
            ]
        )
        session.request = AsyncMock(return_value=sse_resp)

        parts = []
        async for delta in await client.chat_stream([{"role": "user", "content": "Hi"}]):
            parts.append(delta)

        assert parts == ["actual"]

    @pytest.mark.asyncio
    async def test_skips_invalid_json(self):
        session = MagicMock(spec=aiohttp.ClientSession)
        client = BridgeClient(session, "http://bridge:18780", "tok")

        sse_resp = MockSSEResponse(
            [
                "data: not json\n",
                _sse_line("valid"),
                "data: [DONE]\n",
            ]
        )
        session.request = AsyncMock(return_value=sse_resp)

        parts = []
        async for delta in await client.chat_stream([{"role": "user", "content": "Hi"}]):
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

        session.request = AsyncMock(side_effect=TimeoutError())

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

        sse_resp = MockSSEResponse(
            [
                _sse_line("text"),
                "data: [DONE]\n",
            ]
        )
        session.request = AsyncMock(return_value=sse_resp)

        async for _ in await client.chat_stream([{"role": "user", "content": "Hi"}]):
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

        result = await _stream_chat(client, [{"role": "user", "content": "Hi"}], agent="cora")
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

        result = await _stream_chat(client, [{"role": "user", "content": "Hi"}])
        assert result is None


class TestToDeltaStream:
    """US0033: adapt bridge text deltas to HA AssistantContentDeltaDict stream."""

    @pytest.mark.asyncio
    async def test_role_then_content_chunks(self):
        async def deltas():
            for c in ["Hello", " ", "world"]:
                yield c

        out = [d async for d in _to_delta_stream(deltas())]
        assert out[0] == {"role": "assistant"}
        assert out[1:] == [{"content": "Hello"}, {"content": " "}, {"content": "world"}]

    @pytest.mark.asyncio
    async def test_empty_chunks_skipped(self):
        async def deltas():
            for c in ["", "hi", ""]:
                yield c

        out = [d async for d in _to_delta_stream(deltas())]
        assert out == [{"role": "assistant"}, {"content": "hi"}]

    @pytest.mark.asyncio
    async def test_no_chunks_still_yields_role(self):
        async def deltas():
            return
            yield  # make it an async generator

        out = [d async for d in _to_delta_stream(deltas())]
        assert out == [{"role": "assistant"}]


class TestConfirmMarkerStreaming:
    """BG0012: a leading [confirm:LEVEL] marker is stripped BEFORE any delta
    reaches the ChatLog/TTS stream, and the severity is surfaced to the caller."""

    @staticmethod
    async def _run(chunks, holder=None):
        async def deltas():
            for c in chunks:
                yield c

        return [d async for d in _to_delta_stream(deltas(), holder)]

    @pytest.mark.asyncio
    async def test_marker_split_across_chunks_stripped(self):
        holder = {}
        out = await self._run(["[confirm:", "high] ", "Shall I unlock", " the door?"], holder)
        assert out[0] == {"role": "assistant"}
        text = "".join(d["content"] for d in out[1:])
        assert "[confirm:" not in text
        assert text == "Shall I unlock the door?"
        assert holder.get("severity") == "high"

    @pytest.mark.asyncio
    async def test_marker_in_single_chunk_stripped(self):
        holder = {}
        out = await self._run(["[confirm:normal] All good?"], holder)
        assert [d for d in out[1:]] == [{"content": "All good?"}]
        assert holder.get("severity") == "normal"

    @pytest.mark.asyncio
    async def test_unknown_level_left_untouched(self):
        holder = {}
        out = await self._run(["[confirm:banana] hm"], holder)
        text = "".join(d["content"] for d in out[1:])
        assert text == "[confirm:banana] hm"
        assert holder.get("severity") is None

    @pytest.mark.asyncio
    async def test_no_marker_stream_unchanged(self):
        holder = {}
        out = await self._run(["Hello", " ", "world"], holder)
        assert out == [
            {"role": "assistant"},
            {"content": "Hello"},
            {"content": " "},
            {"content": "world"},
        ]
        assert holder.get("severity") is None

    @pytest.mark.asyncio
    async def test_marker_only_stream(self):
        holder = {}
        out = await self._run(["[confirm:high]"], holder)
        assert out == [{"role": "assistant"}]
        assert holder.get("severity") == "high"

    @pytest.mark.asyncio
    async def test_plain_bracket_text_not_swallowed(self):
        holder = {}
        out = await self._run(["[con", "sider] this"], holder)
        text = "".join(d["content"] for d in out[1:])
        assert text == "[consider] this"
        assert holder.get("severity") is None

    @pytest.mark.asyncio
    async def test_severity_holder_optional(self):
        out = await self._run(["[confirm:low] ok"])
        assert [d for d in out[1:]] == [{"content": "ok"}]
