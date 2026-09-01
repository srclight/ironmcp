"""serve_http: bearer-guarded /mcp, an open /healthz naming a capability, fail-closed on an
empty/whitespace token, and — the one that matters — a REAL reachability round-trip proving
/mcp answers (the lifespan is forwarded), not merely that the port binds."""
import importlib.util
import socket
import threading
import time

import pytest

_HAS = all(importlib.util.find_spec(m) for m in ("mcp.server.mcpserver", "httpx", "starlette", "uvicorn"))
pytestmark = pytest.mark.skipif(not _HAS, reason="mcp v2 + httpx + starlette + uvicorn required")


def _server():
    from ironmcp import strict_server

    app = strict_server(name="probe", version="0.0.0")

    @app.tool()
    async def echo(a: str) -> str:
        return a

    return app


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.mark.asyncio
async def test_healthz_open_and_names_capability():
    import httpx

    from ironmcp import build_http_app

    app = build_http_app(_server(), token="secret", capabilities={"strict_args": True})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/healthz")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert isinstance(body["code_sha"], str)
        assert body["capabilities"]["strict_args"] is True


@pytest.mark.asyncio
async def test_mcp_requires_bearer():
    import httpx

    from ironmcp import build_http_app

    app = build_http_app(_server(), token="secret")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        assert (await c.post("/mcp", json={})).status_code == 401
        assert (await c.post("/mcp", json={}, headers={"Authorization": "Bearer WRONG"})).status_code == 401


def test_build_http_app_fails_closed_on_empty_token():
    from ironmcp import build_http_app

    with pytest.raises(ValueError):
        build_http_app(_server(), token="")


def test_build_http_app_fails_closed_on_whitespace_token():
    from ironmcp import build_http_app

    with pytest.raises(ValueError):
        build_http_app(_server(), token="   ")


def test_healthz_reports_caller_supplied_code_sha():
    from starlette.testclient import TestClient

    from ironmcp import build_http_app

    app = build_http_app(_server(), token="secret", code_sha="deadbeef")
    with TestClient(app) as client:
        assert client.get("/healthz").json()["code_sha"] == "deadbeef"


@pytest.mark.asyncio
async def test_mcp_is_reachable_over_a_real_server():
    """The committed reachability proof: a real uvicorn server, a real streamable-HTTP client,
    /mcp answers with the fixture tool. ASGITransport does not run the lifespan, so only this
    test proves the session manager started and /mcp responds."""
    import httpx
    import uvicorn
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    from ironmcp import build_http_app

    port = _free_port()
    app = build_http_app(_server(), token="tok")
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        for _ in range(40):
            if server.started:
                break
            time.sleep(0.1)
        client = httpx.AsyncClient(headers={"Authorization": "Bearer tok"})
        async with streamable_http_client(f"http://127.0.0.1:{port}/mcp", http_client=client) as st:
            async with ClientSession(st[0], st[1]) as s:
                await s.initialize()
                names = [t.name for t in (await s.list_tools()).tools]
                assert names == ["echo"]
        await client.aclose()
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def test_allowed_hosts_layers_a_host_guard_in_front_of_bearer():
    """build_http_app(..., allowed_hosts=...) puts a default-deny HostGuard in FRONT of the
    bearer: an unlisted Host is 403 before auth runs; a listed Host with no token reaches the
    bearer 401."""
    from starlette.testclient import TestClient

    from ironmcp import build_http_app

    app = build_http_app(_server(), token="secret", allowed_hosts=["good.local"])
    with TestClient(app) as client:
        # /mcp: a rebinding host is 403 before the bearer runs; a listed host with no token
        # reaches the bearer 401. The guard sits in FRONT of the bearer (invariant #4).
        assert client.post("/mcp", json={}, headers={"Host": "evil.example.com"}).status_code == 403
        assert client.post("/mcp", json={}, headers={"Host": "good.local"}).status_code == 401
        # /healthz is the deliberately-open route (a sibling of the guarded mount), so it
        # answers regardless of Host — the guard fronts the bearer, not the health probe.
        assert client.get("/healthz", headers={"Host": "good.local"}).status_code == 200


def test_healthz_false_omits_the_health_route():
    from starlette.testclient import TestClient

    from ironmcp import build_http_app

    app = build_http_app(_server(), token="secret", healthz=False)
    with TestClient(app) as client:
        # no /healthz route: the request falls through to the bearer-guarded mount -> 401
        assert client.get("/healthz").status_code == 401


def test_default_capabilities_when_none_supplied():
    """capabilities=None -> the built-in default {'strict_args':True,'ironmcp':True}."""
    from starlette.testclient import TestClient

    from ironmcp import build_http_app

    app = build_http_app(_server(), token="secret")  # capabilities omitted
    with TestClient(app) as client:
        caps = client.get("/healthz").json()["capabilities"]
        assert caps == {"strict_args": True, "ironmcp": True}
