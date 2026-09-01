"""Supervised streamable-HTTP serving in one call: a bearer-guarded ``/mcp``, an open
``/healthz`` that names a capability, and the session-manager lifespan forwarded so the port
actually answers (not merely binds). Fails closed on an empty or whitespace-only token.

The strict-args guarantee is transport-agnostic; this is the deployment glue that every
hardened HTTP MCP server otherwise hand-rolls (auth + health + the lifespan gotcha). Pass your
own ``code_sha`` (a git revision) so ``/healthz`` detects a daemon running edited code — the
built-in default only hashes the kit version.
"""
from __future__ import annotations

from typing import Any

from .auth import make_bearer_asgi
from .health import code_sha as _code_sha


def build_http_app(
    server: Any,
    *,
    token: str,
    healthz: bool = True,
    capabilities: dict | None = None,
    code_sha: str | None = None,
) -> Any:
    """Compose the ASGI app: /healthz open (if enabled), everything else bearer-guarded, the
    mounted streamable-HTTP app's lifespan forwarded. Raises ValueError on an empty/whitespace
    token — HTTP serving fails closed."""
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Mount, Route

    token = (token or "").strip()
    if not token:
        raise ValueError("serve_http token must be non-empty — HTTP serving fails closed")

    mcp_app = server.streamable_http_app()
    guarded = make_bearer_asgi(mcp_app, expected_token=token)
    caps = capabilities or {"strict_args": True, "ironmcp": True}
    sha = code_sha or _code_sha()

    async def _healthz(_request):
        return JSONResponse(
            {"ok": True, "code_sha": sha, "transport": "streamable-http", "capabilities": caps}
        )

    routes = [Mount("/", app=guarded)]
    if healthz:
        routes.insert(0, Route("/healthz", _healthz, methods=["GET"]))
    return Starlette(routes=routes, lifespan=lambda _a: mcp_app.router.lifespan_context(mcp_app))


def serve_http(
    server: Any,
    *,
    token: str,
    host: str = "127.0.0.1",
    port: int,
    healthz: bool = True,
    capabilities: dict | None = None,
    code_sha: str | None = None,
) -> None:
    """Build the composite app and run it under uvicorn. Fails closed on an empty token."""
    import uvicorn

    uvicorn.run(
        build_http_app(
            server, token=token, healthz=healthz, capabilities=capabilities, code_sha=code_sha
        ),
        host=host,
        port=port,
    )
