"""Tests for the bridge client HTTP communication."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.agent_bridge.client import (
    BridgeAuthError,
    BridgeCallerError,
    BridgeClient,
    BridgeConnectionError,
    BridgeError,
    BridgeTimeoutError,
)


@pytest.fixture
def client():
    """Create a BridgeClient with a mocked session."""
    session = MagicMock(spec=aiohttp.ClientSession)
    return BridgeClient(session, "http://bridge:18780", "test-token", timeout=10, ssl_verify=True)


@pytest.fixture
def mock_response():
    """Create a mock aiohttp response."""

    def _make(status=200, json_data=None, content_type="application/json", text=""):
        resp = AsyncMock()
        resp.status = status
        resp.content_type = content_type
        resp.json = AsyncMock(return_value=json_data or {})
        resp.text = AsyncMock(return_value=text)
        resp.__aenter__ = AsyncMock(return_value=resp)
        resp.__aexit__ = AsyncMock(return_value=False)
        return resp

    return _make


class TestBridgeClientInit:
    def test_url_trailing_slash_stripped(self):
        session = MagicMock()
        c = BridgeClient(session, "http://bridge:18780/", "tok")
        assert c._base_url == "http://bridge:18780"

    def test_auth_header_set(self):
        session = MagicMock()
        c = BridgeClient(session, "http://bridge:18780", "my-token")
        assert c._headers == {"Authorization": "Bearer my-token"}

    def test_ssl_verify_false(self):
        session = MagicMock()
        c = BridgeClient(session, "http://bridge:18780", "tok", ssl_verify=False)
        assert c._ssl is False

    def test_ssl_verify_true(self):
        session = MagicMock()
        c = BridgeClient(session, "http://bridge:18780", "tok", ssl_verify=True)
        assert c._ssl is None


class TestCheckAlive:
    @pytest.mark.asyncio
    async def test_returns_true_on_success(self, client, mock_response):
        resp = mock_response(json_data={"status": "ok"})
        client._session.request = MagicMock(return_value=resp)
        assert await client.check_alive() is True

    @pytest.mark.asyncio
    async def test_returns_false_on_error(self, client, mock_response):
        resp = mock_response(status=500, json_data={"error": {"code": "FAIL"}})
        client._session.request = MagicMock(return_value=resp)
        assert await client.check_alive() is False


class TestHealth:
    @pytest.mark.asyncio
    async def test_shallow_health(self, client, mock_response):
        health_data = {"status": "ok", "agents": {"total": 3, "healthy": 3}}
        resp = mock_response(json_data=health_data)
        client._session.request = MagicMock(return_value=resp)
        result = await client.health(depth="shallow")
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_deep_health(self, client, mock_response):
        health_data = {"status": "ok", "agents": {"cora": {"status": "healthy"}}}
        resp = mock_response(json_data=health_data)
        client._session.request = MagicMock(return_value=resp)
        result = await client.health(depth="deep")
        assert "cora" in result["agents"]


class TestDiscover:
    @pytest.mark.asyncio
    async def test_returns_agent_list(self, client, mock_response):
        agents = [{"id": "cora", "name": "Cora"}]
        resp = mock_response(json_data={"agents": agents})
        client._session.request = MagicMock(return_value=resp)
        result = await client.discover()
        assert len(result) == 1
        assert result[0]["id"] == "cora"

    @pytest.mark.asyncio
    async def test_empty_agents(self, client, mock_response):
        resp = mock_response(json_data={"agents": []})
        client._session.request = MagicMock(return_value=resp)
        result = await client.discover()
        assert result == []

    @pytest.mark.asyncio
    async def test_missing_agents_key(self, client, mock_response):
        resp = mock_response(json_data={})
        client._session.request = MagicMock(return_value=resp)
        result = await client.discover()
        assert result == []


class TestChat:
    @pytest.mark.asyncio
    async def test_sends_messages(self, client, mock_response):
        chat_data = {
            "choices": [{"message": {"content": "Hello"}}],
            "agent": "cora",
            "model": "test",
        }
        resp = mock_response(json_data=chat_data)
        client._session.request = MagicMock(return_value=resp)

        result = await client.chat(
            [{"role": "user", "content": "Hi"}],
            agent="cora",
            channel="session-1",
            caller_context={"source_type": "voice"},
        )
        assert result["agent"] == "cora"

    @pytest.mark.asyncio
    async def test_sends_attachments(self, client, mock_response):
        resp = mock_response(json_data={"agent": "cora"})
        client._session.request = MagicMock(return_value=resp)

        await client.chat(
            [{"role": "user", "content": "what's this?"}],
            agent="cora",
            attachments=[{"id": "a1", "mime_type": "image/jpeg", "base64": "AAA"}],
        )
        body = client._session.request.call_args.kwargs["json"]
        assert body["attachments"][0]["mime_type"] == "image/jpeg"
        assert body["attachments"][0]["base64"] == "AAA"


class TestInvokeTool:
    @pytest.mark.asyncio
    async def test_invoke_tool(self, client, mock_response):
        resp = mock_response(json_data={"result": "ok"})
        client._session.request = MagicMock(return_value=resp)
        result = await client.invoke_tool("cora", "web_search", {"q": "test"})
        assert result["result"] == "ok"

    @pytest.mark.asyncio
    async def test_invoke_tool_body_field_names(self, client, mock_response):
        """US0022/G6: body keys are {agent, tool, args}, not agent_id/tool_name."""
        resp = mock_response(json_data={"ok": True})
        client._session.request = MagicMock(return_value=resp)
        await client.invoke_tool("cora", "web_search", {"q": "test"})

        body = client._session.request.call_args.kwargs["json"]
        assert body == {"agent": "cora", "tool": "web_search", "args": {"q": "test"}}
        assert "agent_id" not in body and "tool_name" not in body


class TestBroadcast:
    @pytest.mark.asyncio
    async def test_broadcast_body_shape_and_default_tags(self, client, mock_response):
        """US0022/G5: body is {messages:[{role,content}], tags} with non-empty tags."""
        resp = mock_response(json_data={"responses": {}})
        client._session.request = MagicMock(return_value=resp)
        await client.broadcast("hello all")

        body = client._session.request.call_args.kwargs["json"]
        assert body["messages"] == [{"role": "user", "content": "hello all"}]
        assert body["tags"] == ["operator"]  # default, non-empty (requireTags)
        assert "message" not in body

    @pytest.mark.asyncio
    async def test_broadcast_explicit_tags(self, client, mock_response):
        resp = mock_response(json_data={"responses": {}})
        client._session.request = MagicMock(return_value=resp)
        await client.broadcast("hi", tags=["ops", "alerts"])

        body = client._session.request.call_args.kwargs["json"]
        assert body["tags"] == ["ops", "alerts"]


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_401_raises_auth_error(self, client, mock_response):
        resp = mock_response(status=401)
        client._session.request = MagicMock(return_value=resp)
        with pytest.raises(BridgeAuthError):
            await client.health()

    @pytest.mark.asyncio
    async def test_403_without_caller_signal_raises_auth_error(self, client, mock_response):
        """A bare 403 (no caller-permission signal) is still a token auth failure."""
        resp = mock_response(status=403)
        client._session.request = MagicMock(return_value=resp)
        with pytest.raises(BridgeAuthError) as exc_info:
            await client.health()
        assert not isinstance(exc_info.value, BridgeCallerError)

    @pytest.mark.asyncio
    async def test_403_tool_permission_denied_raises_caller_error(self, client, mock_response):
        """BG0004: 403 + TOOL_PERMISSION_DENIED is a caller-identity problem, not a token one."""
        error_data = {
            "error": {
                "code": "TOOL_PERMISSION_DENIED",
                "message": "Caller 'homeassistant' is not a registered agent",
            }
        }
        resp = mock_response(status=403, json_data=error_data)
        client._session.request = MagicMock(return_value=resp)
        with pytest.raises(BridgeCallerError) as exc_info:
            await client.chat([{"role": "user", "content": "ping"}], agent="cora")
        assert exc_info.value.code == "CALLER_ERROR"
        assert "not a registered agent" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_403_caller_message_without_known_code_raises_caller_error(
        self, client, mock_response
    ):
        """Classification also keys off the message text, for unknown error codes."""
        error_data = {"error": {"code": "SOME_OTHER", "message": "Unknown caller identity"}}
        resp = mock_response(status=403, json_data=error_data)
        client._session.request = MagicMock(return_value=resp)
        with pytest.raises(BridgeCallerError):
            await client.chat([{"role": "user", "content": "ping"}], agent="cora")

    @pytest.mark.asyncio
    async def test_401_is_never_a_caller_error(self, client, mock_response):
        """401 is always a token problem, regardless of body."""
        error_data = {"error": {"code": "TOOL_PERMISSION_DENIED", "message": "caller"}}
        resp = mock_response(status=401, json_data=error_data)
        client._session.request = MagicMock(return_value=resp)
        with pytest.raises(BridgeAuthError) as exc_info:
            await client.health()
        assert not isinstance(exc_info.value, BridgeCallerError)

    @pytest.mark.asyncio
    async def test_timeout_raises_timeout_error(self, client):
        client._session.request = MagicMock(side_effect=TimeoutError())
        with pytest.raises(BridgeTimeoutError):
            await client.health()

    @pytest.mark.asyncio
    async def test_connection_error_raises(self, client):
        client._session.request = MagicMock(side_effect=aiohttp.ClientError("refused"))
        with pytest.raises(BridgeConnectionError):
            await client.health()

    @pytest.mark.asyncio
    async def test_http_error_with_error_body(self, client, mock_response):
        error_data = {"error": {"code": "AGENT_TIMEOUT", "message": "timed out"}}
        resp = mock_response(status=500, json_data=error_data)
        client._session.request = MagicMock(return_value=resp)
        with pytest.raises(BridgeError) as exc_info:
            await client.health()
        assert exc_info.value.code == "AGENT_TIMEOUT"

    @pytest.mark.asyncio
    async def test_non_json_response(self, client, mock_response):
        resp = mock_response(status=200, content_type="text/html", text="<html>")
        client._session.request = MagicMock(return_value=resp)
        with pytest.raises(BridgeError) as exc_info:
            await client.health()
        assert exc_info.value.code == "INVALID_RESPONSE"


class TestExceptionClasses:
    def test_bridge_error(self):
        err = BridgeError("CODE", "message")
        assert err.code == "CODE"
        assert str(err) == "message"

    def test_bridge_connection_error(self):
        err = BridgeConnectionError()
        assert err.code == "CONNECTION_ERROR"

    def test_bridge_auth_error(self):
        err = BridgeAuthError()
        assert err.code == "AUTH_ERROR"

    def test_bridge_caller_error(self):
        err = BridgeCallerError()
        assert err.code == "CALLER_ERROR"
        assert isinstance(err, BridgeError)
        assert not isinstance(err, BridgeAuthError)

    def test_bridge_timeout_error(self):
        err = BridgeTimeoutError()
        assert err.code == "TIMEOUT"
