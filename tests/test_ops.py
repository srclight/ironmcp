"""Health must be reachable WITHOUT an MCP session; bearer must fail closed."""

import os

import pytest
from starlette.testclient import TestClient

from mcpkit import (EX_CONFIG, StrictArgsMCP, attach_healthz, bearer_middleware,
                    code_sha, require_token_or_exit)


def _app(*, token: str | None = None, probes=None):
    srv = StrictArgsMCP("test")

    @srv.tool()
    def noop(x: str) -> str:
        return x

    attach_healthz(srv, name="test", probes=probes)
    app = srv.streamable_http_app()
    if token:
        app.add_middleware(bearer_middleware(token))
    return app


def test_healthz_answers_without_an_mcp_session():
    """The whole point: a check that needs a working session cannot report a broken one."""
    with TestClient(_app()) as c:
        r = c.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["pid"] == os.getpid()
    assert "code_sha" in body          # present even when None -- absence is reported, not hidden
    assert body["uptime_s"] >= 0


def test_healthz_is_never_cached():
    with TestClient(_app()) as c:
        r = c.get("/healthz")
    assert r.headers.get("cache-control") == "no-store"


def test_healthz_reports_a_failing_probe_rather_than_throwing():
    """A health endpoint that dies with the thing it monitors reports nothing."""
    def boom() -> bool:
        raise RuntimeError("db is gone")

    with TestClient(_app(probes={"db": boom})) as c:
        r = c.get("/healthz")
    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert r.json()["probes"]["db"] is False


def test_bearer_rejects_missing_and_wrong_tokens():
    app = _app(token="secret-token")
    with TestClient(app) as c:
        assert c.post("/mcp", json={}).status_code == 401
        assert c.post("/mcp", json={}, headers={"Authorization": "Bearer wrong"}).status_code == 401
        # A correct token must NOT be rejected by the auth layer. Any non-401 proves the request
        # reached the app; the MCP layer's own opinion of an empty body is irrelevant here.
        assert c.post("/mcp", json={}, headers={"Authorization": "Bearer secret-token"}).status_code != 401


def test_healthz_stays_open_when_bearer_is_on():
    """By design: a restart script must verify what came up without holding a credential."""
    with TestClient(_app(token="secret-token")) as c:
        assert c.get("/healthz").status_code == 200


def test_deployed_path_fails_closed_without_a_token():
    with pytest.raises(SystemExit) as e:
        require_token_or_exit(None, transport="streamable-http", service="test")
    # 78 not 1: a misconfiguration, pairing with systemd RestartPreventExitStatus=78 so the unit
    # STOPS rather than looping a broken config into place.
    assert e.value.code == EX_CONFIG


def test_stdio_needs_no_token_and_http_with_token_proceeds():
    require_token_or_exit(None, transport="stdio", service="test")       # must not raise
    require_token_or_exit("t", transport="streamable-http", service="test")


def test_code_sha_is_stable_within_a_process():
    """Stamped once at import. A value that moves under a running process is the lie being guarded."""
    assert code_sha() == code_sha()
