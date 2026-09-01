"""F7 host-guard: DNS-rebinding allowlist ON by default (default-deny), alongside the
existing constant-time bearer (#4)."""

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from ironmcp import HostGuard, make_bearer_asgi, make_host_guard_asgi

ALLOWED = ["localhost", "127.0.0.1", "wasabi.local"]


# --- the pure predicate (mirrors the Dart HostGuard group) --------------------


def test_accepts_an_allowed_host_with_or_without_a_port():
    g = HostGuard(allowed_hosts=ALLOWED)
    assert g.accepts("localhost") is True
    assert g.accepts("localhost:8080") is True
    assert g.accepts("wasabi.local:18888") is True


def test_rejects_a_rebinding_attacker_host_and_a_null_empty_host():
    g = HostGuard(allowed_hosts=ALLOWED)
    assert g.accepts("evil.example.com") is False
    assert g.accepts("evil.example.com:8080") is False
    assert g.accepts(None) is False
    assert g.accepts("") is False


def test_portless_match_can_be_disabled():
    g = HostGuard(allowed_hosts=["localhost"], allow_portless_match=False)
    assert g.accepts("localhost") is True
    assert g.accepts("localhost:8080") is False


# --- the ASGI wrapper: default-deny 403 ---------------------------------------


def _inner():
    async def ok(request):
        return PlainTextResponse("reached")

    return Starlette(routes=[Route("/", ok)])


def _host_client(allowed):
    return TestClient(make_host_guard_asgi(_inner(), allowed_hosts=allowed))


def test_disallowed_host_is_403_before_the_app_runs():
    # TestClient default Host is "testserver" — not allow-listed.
    r = _host_client(["localhost"]).get("/")
    assert r.status_code == 403


def test_allowed_host_reaches_the_app():
    r = _host_client(["testserver"]).get("/")
    assert r.status_code == 200
    assert r.text == "reached"


def test_host_guard_sits_in_front_of_bearer():
    """A rebinding host is refused (403) before the bearer (401) ever runs, and a valid
    host with no token still hits the bearer 401."""
    guarded = make_host_guard_asgi(
        make_bearer_asgi(_inner(), expected_token="tok"),
        allowed_hosts=["good.local"],
    )
    client = TestClient(guarded)
    # bad host -> 403 (host guard wins, before auth)
    assert client.get("/", headers={"Host": "evil.example.com"}).status_code == 403
    # good host, no token -> 401 (reaches the bearer)
    assert client.get("/", headers={"Host": "good.local"}).status_code == 401
    # good host + token -> 200
    assert (
        client.get(
            "/", headers={"Host": "good.local", "Authorization": "Bearer tok"}
        ).status_code
        == 200
    )
