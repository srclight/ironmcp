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


# --- host matching is case-INSENSITIVE (RFC 7230) -------------------------------------


def test_host_match_is_case_insensitive_incoming_host():
    g = HostGuard(allowed_hosts=["localhost", "wasabi.local"])
    assert g.accepts("Localhost") is True
    assert g.accepts("LOCALHOST:8080") is True
    assert g.accepts("Wasabi.Local:18888") is True


def test_host_match_is_case_insensitive_allowlist_entry():
    """A mixed-case allowlist entry still matches a lower-case incoming host."""
    g = HostGuard(allowed_hosts=["LocalHost"])
    assert g.accepts("localhost") is True
    assert g.accepts("localhost:9000") is True


# --- bracketed IPv6 literals: strip the port only AFTER the closing ] ------------------


def test_accepts_bracketed_ipv6_literal_with_and_without_a_port():
    """A naive host.split(':',1)[0] turns '[::1]:8080' into '[' and locks out an IPv6 loopback
    server. The port must be stripped only after the closing bracket."""
    g = HostGuard(allowed_hosts=["[::1]"])
    assert g.accepts("[::1]") is True
    assert g.accepts("[::1]:8080") is True
    # a different IPv6 literal is still refused
    assert g.accepts("[::2]:8080") is False


def test_bracketed_ipv6_match_is_case_insensitive_and_full_address():
    g = HostGuard(allowed_hosts=["[fe80::1]"])
    assert g.accepts("[FE80::1]") is True
    assert g.accepts("[fe80::1]:18888") is True


# --- non-HTTP scopes pass through BOTH ASGI wrappers untouched -------------------------


@pytest.mark.asyncio
async def test_non_http_scope_passes_through_both_wrappers():
    async def _noop_recv():
        return {}

    async def _noop_send(_m):
        return None

    for wrap in (
        lambda inner: make_bearer_asgi(inner, expected_token="tok"),
        lambda inner: make_host_guard_asgi(inner, allowed_hosts=["good.local"]),
    ):
        reached = {"v": False}

        async def inner(scope, receive, send):
            reached["v"] = True

        guarded = wrap(inner)
        # a websocket scope carries no auth/host checks — it must pass straight through
        await guarded({"type": "websocket"}, _noop_recv, _noop_send)
        assert reached["v"] is True
        # a lifespan scope likewise passes through
        reached["v"] = False
        await guarded({"type": "lifespan"}, _noop_recv, _noop_send)
        assert reached["v"] is True
