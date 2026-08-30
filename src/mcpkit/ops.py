"""Operational surface: a session-free health endpoint and fail-closed bearer auth.

BOTH ARE OPT-IN AND HTTP-ONLY. A stdio server has no port to protect and no route to serve.

WHY HEALTH MUST NOT BE A TOOL. loqu8-dart's McpServiceBase registers ``health`` via
``registerTool`` -- reachable only THROUGH the MCP session. A health check that lives inside the
session cannot report that the session is the broken thing; it goes silent exactly when it is
needed, and silence is indistinguishable from "not asked". Proven on 2026-08-28: an 8744 process
that was healthy, held a valid LISTEN socket, and was unreachable by anything on the machine. Every
process-level check reported green.

WHY NO DB PING IN THE DEFAULT. A blocked accept loop is precisely what a heavy health check cannot
report -- it blocks too. Callers may pass cheap probes explicitly; the default stays cheap.
"""

from __future__ import annotations

import os
from typing import Any, Callable, Mapping

from .build import code_sha, started_at, uptime_s


def _mcpkit_version() -> str:
    from . import __version__
    return __version__

__all__ = ["attach_healthz", "bearer_middleware", "require_token_or_exit", "EX_CONFIG"]

# sysexits.h EX_CONFIG. Pairs with systemd RestartPreventExitStatus=78 so a misconfigured unit
# STOPS rather than looping a broken config into place.
EX_CONFIG = 78

HEALTH_PATH = "/healthz"


def attach_healthz(
    mcp: Any,
    *,
    name: str | None = None,
    probes: Mapping[str, Callable[[], bool]] | None = None,
    path: str = HEALTH_PATH,
) -> None:
    """Register a session-free GET endpoint reporting what this process is.

    ``probes`` are optional named callables returning bool. Keep them cheap; anything that can
    block belongs outside the health path.
    """
    from starlette.responses import JSONResponse

    @mcp.custom_route(path, methods=["GET"])
    async def _healthz(request):  # noqa: ANN001
        results: dict[str, bool] = {}
        ok = True
        for pname, probe in (probes or {}).items():
            try:
                results[pname] = bool(probe())
            except Exception:
                results[pname] = False
            ok = ok and results[pname]
        return JSONResponse(
            {
                "ok": ok,
                "name": name or getattr(mcp, "name", None),
                "pid": os.getpid(),
                "code_sha": code_sha(),
                # A chassis adds a SECOND version axis. Without it the first cross-version bug
                # is undiagnosable from outside: "which server is on which mcpkit" has no answer.
                "mcpkit_version": _mcpkit_version(),
                "started_at": started_at(),
                "uptime_s": round(uptime_s(), 3),
                **({"probes": results} if results else {}),
            },
            headers={"Cache-Control": "no-store"},  # a cached health check is not a health check
        )


def bearer_middleware(token: str, *, exempt: tuple[str, ...] = (HEALTH_PATH,)):
    """Starlette middleware requiring ``Authorization: Bearer <token>``.

    ``/healthz`` is exempt BY DESIGN: a restart script must be able to verify what came up without
    holding a credential, and the health payload carries no corpus data.
    """
    import hmac
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse

    class _Bearer(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):  # noqa: ANN001
            if request.url.path in exempt:
                return await call_next(request)
            got = request.headers.get("authorization", "")
            prefix = "Bearer "
            # compare_digest, not ==: an early-exit comparison leaks the token a byte at a time.
            if not (got.startswith(prefix) and hmac.compare_digest(got[len(prefix):], token)):
                # WWW-Authenticate on the 401 is what the MCP spec's OAuth flow expects: it names
                # the scheme the client must use, so a compliant client knows HOW to retry rather
                # than only THAT it failed. The scheme is Bearer; there is no realm to leak.
                return JSONResponse(
                    {"error": "unauthorized"}, status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return await call_next(request)

    return _Bearer


def require_token_or_exit(token: str | None, *, transport: str, service: str) -> None:
    """FAIL CLOSED on the deployed path. Call this from the entry point, not the library.

    Under WSL2 with networkingMode=mirrored a 127.0.0.1 bind is reachable from any normal-privilege
    Windows process -- demonstrated 2026-08-28, when a PowerShell request read restricted corpus
    text with no credential. "Loopback" is not the boundary it sounds like here.

    The library default stays permissive so tests and ad-hoc runs are unaffected; only the
    supervised entry point refuses, which is what keeps this from becoming a test tax.
    """
    if transport == "stdio" or token:
        return
    import sys

    print(
        f"{service}: refusing to start on {transport} without a bearer token.\n"
        "This port is reachable from the Windows host under mirrored networking.\n"
        "Set the token in the unit's EnvironmentFile, or run stdio for local debugging.",
        file=sys.stderr,
    )
    raise SystemExit(EX_CONFIG)
