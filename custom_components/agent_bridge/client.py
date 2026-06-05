"""Async HTTP client for the Agent Bridge REST API."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

import aiohttp

from .const import DEFAULT_STREAMING_TIMEOUT, DEFAULT_THINKING_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class BridgeError(Exception):
    """Base exception for bridge communication errors."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class BridgeConnectionError(BridgeError):
    """Bridge is unreachable."""

    def __init__(self, message: str = "Bridge is unreachable") -> None:
        super().__init__("CONNECTION_ERROR", message)


class BridgeAuthError(BridgeError):
    """Authentication failed -- the bridge token is missing, wrong, or expired."""

    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__("AUTH_ERROR", message)


class BridgeCallerError(BridgeError):
    """Caller identity rejected -- the ``x-bridge-mcp-caller`` agent is not registered.

    Distinct from :class:`BridgeAuthError`: the token is valid, but bridge v4.36
    cannot resolve the caller's crew for cross-agent dispatch because the caller id
    is not a registered agent (BG0004). Surfaced separately so the user is pointed
    at the caller configuration rather than the token.
    """

    def __init__(self, message: str = "Caller identity not recognised by bridge") -> None:
        super().__init__("CALLER_ERROR", message)


# Bridge error codes that mean "the caller identity is not authorised", not "bad token".
_CALLER_ERROR_CODES = {"TOOL_PERMISSION_DENIED", "CALLER_NOT_REGISTERED", "CREW_RESOLUTION_FAILED"}


def _is_caller_permission_error(code: str | None, message: str | None) -> bool:
    """Classify a 403 as a caller-identity problem rather than a token problem."""
    if code and code.upper() in _CALLER_ERROR_CODES:
        return True
    if message:
        lowered = message.lower()
        if "not a registered agent" in lowered or "caller" in lowered:
            return True
    return False


class BridgeTimeoutError(BridgeError):
    """Request timed out."""

    def __init__(self, message: str = "Request timed out") -> None:
        super().__init__("TIMEOUT", message)


class BridgeClient:
    """Async HTTP client for the Agent Bridge REST API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        token: str,
        *,
        timeout: int = DEFAULT_THINKING_TIMEOUT,
        ssl_verify: bool = True,
        caller_id: str | None = None,
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}
        # v4.36 crew-aware caller identity (US0028/G9). Sent on every request so the
        # bridge can scope discovery/selection to this caller's crew.
        if caller_id:
            self._headers["x-bridge-mcp-caller"] = caller_id
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._ssl: bool | None = None if ssl_verify else False

    @staticmethod
    async def _error_payload(
        resp: aiohttp.ClientResponse,
    ) -> tuple[str | None, str | None]:
        """Best-effort ``(code, message)`` from an error response body."""
        try:
            if resp.content_type and "json" in resp.content_type:
                data = await resp.json()
                error = data.get("error", {}) if isinstance(data, dict) else {}
                if isinstance(error, dict):
                    return error.get("code"), error.get("message")
        except (aiohttp.ClientError, ValueError):
            pass
        return None, None

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        auth: bool = True,
        timeout: aiohttp.ClientTimeout | None = None,
    ) -> dict[str, Any]:
        """Make an HTTP request to the bridge."""
        url = f"{self._base_url}{path}"
        headers = self._headers if auth else {}
        request_timeout = timeout or self._timeout

        try:
            async with self._session.request(
                method,
                url,
                json=json,
                headers=headers,
                timeout=request_timeout,
                ssl=self._ssl,
            ) as resp:
                if resp.status == 401:
                    raise BridgeAuthError("Bridge returned 401: authentication failed")
                if resp.status == 403:
                    code, message = await self._error_payload(resp)
                    if _is_caller_permission_error(code, message):
                        raise BridgeCallerError(
                            message or "Bridge rejected the Home Assistant caller identity"
                        )
                    raise BridgeAuthError(message or "Bridge returned 403: authentication failed")

                if resp.content_type and "json" in resp.content_type:
                    data = await resp.json()
                else:
                    text = await resp.text()
                    if not text:
                        raise BridgeError("EMPTY_RESPONSE", "Empty response from bridge")
                    raise BridgeError(
                        "INVALID_RESPONSE",
                        f"Non-JSON response from bridge: {text[:200]}",
                    )

                if resp.status >= 400:
                    error = data.get("error", {}) if isinstance(data, dict) else {}
                    code = error.get("code", f"HTTP_{resp.status}")
                    message = error.get("message", f"Bridge returned HTTP {resp.status}")
                    raise BridgeError(code, message)

                return data

        except BridgeError:
            raise
        except TimeoutError as err:
            raise BridgeTimeoutError(
                f"Bridge request timed out after {request_timeout.total}s"
            ) from err
        except aiohttp.ClientError as err:
            raise BridgeConnectionError(
                f"Cannot connect to bridge at {self._base_url}: {err}"
            ) from err

    async def check_alive(self) -> bool:
        """Lightweight connectivity check via GET /health."""
        try:
            await self._request(
                "GET",
                "/health",
                auth=False,
                timeout=aiohttp.ClientTimeout(total=5),
            )
        except BridgeError:
            return False
        return True

    async def health(self, depth: str = "shallow") -> dict[str, Any]:
        """Get bridge health status.

        Args:
            depth: "shallow" for summary, "deep" for per-agent details.
        """
        return await self._request("GET", f"/health?depth={depth}", auth=False)

    async def discover(self, *, include: list[str] | None = None) -> list[dict[str, Any]]:
        """Get the list of registered agents from the bridge.

        ``include`` requests v4.36 ``?include=`` projection groups (e.g.
        ``["crew"]`` adds each agent's ``crew: {team, visibleCrews}`` block, the
        only place per-agent crew membership is exposed -- CR-0003).
        """
        path = "/v1/discovery"
        if include:
            path = f"{path}?include={','.join(include)}"
        data = await self._request("GET", path)
        agents = data.get("agents", [])
        return agents if isinstance(agents, list) else []

    async def agent_health(self) -> dict[str, Any]:
        """Get the auth-gated ``/v1/health`` view (tri-state + toolSurface).

        v4.36 per-agent readiness lives here, not at ``/health?depth=deep``
        (a phantom -- the handler ignores the query string). Returns the tri-state
        ``bridge`` field plus ``toolSurface``/``readOnlySafe`` (US0028/AC4, G14).
        """
        return await self._request("GET", "/v1/health")

    async def agent_context(self) -> dict[str, Any]:
        """Get ``/v1/agent-context`` -- the bridge's machine-readable changelog.

        Carries ``version``/``notable_capabilities``/``knownIssues``/``deprecations``
        used by the drift check to raise an HA repair issue (US0029/G13).
        """
        return await self._request("GET", "/v1/agent-context")

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        agent: str | None = None,
        channel: str | None = None,
        caller_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a chat completion request to the bridge.

        ``caller_context`` is the structured speaker/source/location envelope
        (who/what/where/when) the bridge records and renders for the agent.
        """
        body: dict[str, Any] = {"messages": messages}
        if agent:
            body["agent"] = agent
        if channel:
            body["channel"] = channel
        if caller_context:
            body["caller_context"] = caller_context
        return await self._request("POST", "/v1/chat/completions", json=body)

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        agent: str | None = None,
        channel: str | None = None,
        caller_context: dict[str, Any] | None = None,
        stream_timeout: int | None = None,
    ) -> AsyncIterator[str]:
        """Send a streaming chat completion request. Yields content delta strings.

        v4.36 SSE format: ``event:message`` / ``data:{"text":"word"}`` frames,
        terminated by an ``event:done`` frame or socket close. The legacy OpenAI
        ``data:{"choices":[{"delta":{"content":...}}]}`` + ``data:[DONE]`` shape is
        still accepted for backward compatibility (US0023/G7).
        """
        body: dict[str, Any] = {"messages": messages, "stream": True}
        if agent:
            body["agent"] = agent
        if channel:
            body["channel"] = channel
        if caller_context:
            body["caller_context"] = caller_context

        url = f"{self._base_url}/v1/chat/completions"
        timeout_val = stream_timeout or DEFAULT_STREAMING_TIMEOUT
        timeout = aiohttp.ClientTimeout(total=timeout_val)

        try:
            resp = await self._session.request(
                "POST",
                url,
                json=body,
                headers=self._headers,
                timeout=timeout,
                ssl=self._ssl,
            )
        except TimeoutError as err:
            raise BridgeTimeoutError(f"Streaming request timed out after {timeout_val}s") from err
        except aiohttp.ClientError as err:
            raise BridgeConnectionError(
                f"Cannot connect to bridge at {self._base_url}: {err}"
            ) from err

        if resp.status == 401:
            resp.close()
            raise BridgeAuthError("Bridge returned 401: authentication failed")
        if resp.status == 403:
            code, message = await self._error_payload(resp)
            resp.close()
            if _is_caller_permission_error(code, message):
                raise BridgeCallerError(
                    message or "Bridge rejected the Home Assistant caller identity"
                )
            raise BridgeAuthError(message or "Bridge returned 403: authentication failed")
        if resp.status >= 400:
            resp.close()
            raise BridgeError(
                f"HTTP_{resp.status}",
                f"Bridge returned HTTP {resp.status} for streaming request",
            )

        return self._iter_sse(resp)

    async def _iter_sse(
        self,
        resp: aiohttp.ClientResponse,
    ) -> AsyncIterator[str]:
        """Iterate over SSE frames, yielding content deltas.

        Tracks the SSE ``event:`` field across lines so the v4.36 bridge's
        ``event:message`` / ``data:{"text":...}`` frames are parsed and
        ``event:done`` terminates the stream — without relying on the
        OpenAI ``data:[DONE]`` sentinel the bridge never sends. The legacy
        ``choices[].delta.content`` + ``[DONE]`` shape still works (US0023/G7).
        """
        import json as _json

        event_type = "message"
        try:
            async for raw_line in resp.content:
                line = raw_line.decode("utf-8", errors="replace").strip()

                if not line:
                    # Blank line ends an SSE frame; reset to the default event.
                    event_type = "message"
                    continue
                if line.startswith(":"):
                    # SSE comment.
                    continue
                if line.startswith("event:"):
                    event_type = line[len("event:") :].strip()
                    if event_type == "done":
                        return
                    continue
                if not line.startswith("data:"):
                    continue

                data_str = line[len("data:") :].strip()
                if data_str == "[DONE]":
                    return

                try:
                    chunk = _json.loads(data_str)
                except (ValueError, TypeError):
                    continue

                # Terminal can also be carried as event:done's data or {"done":true}.
                if event_type == "done" or chunk.get("done") is True:
                    return

                # v4.36 shape: {"text": "word"}.
                text = chunk.get("text")
                if text:
                    yield text
                    continue

                # Legacy OpenAI delta shape: {"choices":[{"delta":{"content":...}}]}.
                choices = chunk.get("choices", [])
                if choices:
                    content = choices[0].get("delta", {}).get("content")
                    if content:
                        yield content
        finally:
            resp.close()

    async def invoke_tool(
        self,
        agent_id: str,
        tool_name: str,
        args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Invoke a tool on a specific agent.

        v4.36 bridge reads ``body.agent``/``body.tool`` (not ``agent_id``/``tool_name``);
        the ``args`` key is unchanged (US0022/G6).
        """
        body: dict[str, Any] = {
            "agent": agent_id,
            "tool": tool_name,
        }
        if args:
            body["args"] = args
        return await self._request("POST", "/v1/tools/invoke", json=body)

    async def broadcast(
        self,
        message: str,
        *,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Broadcast a message to all agents (or a tagged subset).

        v4.36 ``/v1/broadcast`` requires ``{messages:[{role,content}], tags}`` with a
        non-empty ``tags`` array (``requireTags`` defaults true, so a tagless broadcast
        400s). Defaults ``tags`` to ``['operator']`` when none supplied (US0022/G5). The
        bridge returns ``responses`` as an OBJECT keyed by agentId — parsed in services.py.
        """
        body: dict[str, Any] = {
            "messages": [{"role": "user", "content": message}],
            "tags": tags if tags else ["operator"],
        }
        return await self._request("POST", "/v1/broadcast", json=body)

    async def register_webhook(
        self,
        callback_url: str,
        events: list[str],
    ) -> dict[str, Any]:
        """Register a webhook subscription with the bridge."""
        body = {"url": callback_url, "events": events}
        return await self._request("POST", "/v1/webhooks", json=body)

    async def unregister_webhook(self, subscription_id: str) -> dict[str, Any]:
        """Unregister a webhook subscription from the bridge."""
        return await self._request("DELETE", f"/v1/webhooks/{subscription_id}")
