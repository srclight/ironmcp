"""Fail-closed bearer auth at the HTTP transport seam.

Auth gates the CONNECTION, not each tool call — an unauthenticated caller must never
reach tool dispatch, so this is an ASGI wrapper around the server's HTTP app
(``server.streamable_http_app()`` / ``sse_app()``), not a per-tool middleware. A missing
or wrong token gets ``401`` with a ``WWW-Authenticate: Bearer`` header. An empty
``expected_token`` raises at construction — misconfiguration fails CLOSED, never open.
"""

from __future__ import annotations

import hmac
from typing import Any, Awaitable, Callable

__all__ = ["make_bearer_asgi"]

ASGIApp = Callable[[dict, Callable[[], Awaitable], Callable[[dict], Awaitable]], Awaitable]


async def _send_401(send: Callable[[dict], Awaitable]) -> None:
    body = b'{"error":"unauthorized"}'
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"www-authenticate", b"Bearer"),
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


def make_bearer_asgi(app: ASGIApp, *, expected_token: str) -> ASGIApp:
    """Wrap an ASGI app so every HTTP request must carry ``Authorization: Bearer <token>``."""
    if not expected_token:
        raise ValueError("expected_token must be non-empty — bearer auth fails closed")
    expected = expected_token.encode()

    async def guarded(scope: dict, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        value = headers.get(b"authorization", b"")
        token = value[7:] if value[:7].lower() == b"bearer " else b""
        if not (token and hmac.compare_digest(token, expected)):
            await _send_401(send)
            return
        await app(scope, receive, send)

    return guarded
