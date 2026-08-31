"""Bearer auth: fails closed on misconfig; 401 + WWW-Authenticate without a valid token;
passes with the right token."""

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from mcpkit.v2.auth import make_bearer_asgi

TOKEN = "s3cret-token-value"


def _inner_app():
    async def ok(request):
        return PlainTextResponse("reached")

    return Starlette(routes=[Route("/", ok)])


def _client():
    return TestClient(make_bearer_asgi(_inner_app(), expected_token=TOKEN))


def test_empty_token_fails_closed():
    with pytest.raises(ValueError):
        make_bearer_asgi(_inner_app(), expected_token="")


def test_no_header_is_401_with_challenge():
    r = _client().get("/")
    assert r.status_code == 401
    assert r.headers.get("www-authenticate") == "Bearer"


def test_wrong_token_is_401():
    r = _client().get("/", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401


def test_correct_token_reaches_app():
    r = _client().get("/", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200
    assert r.text == "reached"
