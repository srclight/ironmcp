"""Fail-closed bearer auth at the HTTP transport seam.

Auth gates the CONNECTION, not each tool call — an unauthenticated caller must never
reach tool dispatch, so this is an ASGI wrapper around the server's HTTP app
(``server.streamable_http_app()`` / ``sse_app()``), not a per-tool middleware. A missing
or wrong token gets ``401`` with a ``WWW-Authenticate: Bearer`` header. An empty
``expected_token`` raises at construction — misconfiguration fails CLOSED, never open.
"""

from __future__ import annotations

import hmac
from typing import Any, Awaitable, Callable, Iterable

__all__ = ["make_bearer_asgi", "HostGuard", "make_host_guard_asgi"]

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


class HostGuard:
    """DNS-rebinding / host-allowlist guard. Posture is default-DENY (ON by default): a
    request whose ``Host`` header is not in ``allowed_hosts`` is rejected.

    loqu8 bound ``0.0.0.0`` with rebinding OFF while a comment falsely claimed it was on;
    this defaults it ON (invariant #4). Give it the hosts the server legitimately answers as
    (add the WSL/LAN name/IP + ``localhost`` when 0.0.0.0-bound, so WSL reach still works
    while a rebinding attacker's ``Host`` is refused). Ported from
    ``kits/dart/lib/src/auth.dart``.
    """

    def __init__(
        self, *, allowed_hosts: Iterable[str], allow_portless_match: bool = True
    ) -> None:
        self.allowed_hosts = set(allowed_hosts)
        self.allow_portless_match = allow_portless_match

    def accepts(self, host_header: str | None) -> bool:
        """True iff ``host_header`` is allowed. A null/empty host is rejected."""
        if not host_header:
            return False
        if host_header in self.allowed_hosts:
            return True
        if self.allow_portless_match and host_header.split(":", 1)[0] in self.allowed_hosts:
            return True
        return False


async def _send_403(send: Callable[[dict], Awaitable]) -> None:
    body = b'{"error":"forbidden host"}'
    await send(
        {
            "type": "http.response.start",
            "status": 403,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


def make_host_guard_asgi(app: ASGIApp, *, allowed_hosts: Iterable[str]) -> ASGIApp:
    """Wrap an ASGI app so every HTTP request's ``Host`` header must be allow-listed.

    Default-deny (ON by default): an unlisted, missing, or empty ``Host`` gets ``403``. Sits
    ALONGSIDE :func:`make_bearer_asgi` — a rebinding attacker is refused before auth even
    runs. Non-HTTP scopes pass through untouched.
    """
    guard = HostGuard(allowed_hosts=allowed_hosts)

    async def guarded(scope: dict, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        host = headers.get(b"host", b"").decode("latin-1")
        if not guard.accepts(host):
            await _send_403(send)
            return
        await app(scope, receive, send)

    return guarded
