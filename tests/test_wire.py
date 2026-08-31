"""Raw JSON-RPC over HTTP. No SDK client.

A test that exercises the chassis through the same SDK it wraps can share the SDK's own
assumptions. This one sends literal JSON-RPC strings and reads the literal response, so what is
asserted is what a real caller would actually receive.

It also asserts the NEGATIVE side-effect: the tool body must not have run. An error in the response
is not by itself proof that nothing happened.
"""

import json

from starlette.testclient import TestClient

from mcp.server.transport_security import TransportSecuritySettings

from mcpkit import StrictArgsMCP

SIDE_EFFECT: dict[str, int] = {"writes": 0}


def _client():
    # The DNS-rebinding guard is ON by default and correct -- a real deployment gets Host
    # "127.0.0.1:8742", but TestClient sends a bare host with no port, which the guard rejects.
    # Widen it for the test rather than disabling the protection.
    srv = StrictArgsMCP("wire", transport_security=TransportSecuritySettings(
        allowed_hosts=["127.0.0.1", "testserver"], allowed_origins=["http://127.0.0.1"]))

    @srv.tool()
    def scoped_search(query: str, project: str | None = None) -> dict:
        SIDE_EFFECT["writes"] += 1          # stands in for a real mutation
        return {"query": query, "project": project}

    # base_url must be a loopback host: the MCP transport security layer rejects TestClient's
    # default "testserver" Host as a DNS-rebinding attempt. That guard is correct and worth
    # keeping -- the test is what has to adapt.
    return TestClient(srv.streamable_http_app(), base_url="http://127.0.0.1")


def _rpc(c, payload, sid=None):
    h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if sid:
        h["mcp-session-id"] = sid
    r = c.post("/mcp", content=json.dumps(payload), headers=h)
    body = r.text
    for line in body.splitlines():
        if line.startswith("data: "):
            body = line[6:]
            break
    try:
        return r, json.loads(body)
    except Exception:
        return r, {}


def _session(c):
    r, _ = _rpc(c, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2024-11-05", "capabilities": {},
        "clientInfo": {"name": "wire", "version": "1"}}})
    sid = r.headers.get("mcp-session-id")
    if sid:
        _rpc(c, {"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
    return sid


def test_raw_wire_rejects_bogus_argument_and_body_never_runs():
    SIDE_EFFECT["writes"] = 0
    with _client() as c:
        sid = _session(c)
        _, res = _rpc(c, {"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {
            "name": "scoped_search",
            "arguments": {"query": "main", "bogus": 1}}}, sid)

    payload = json.dumps(res)
    # The caller must be able to SEE this. A successful-looking 200 whose text merely fails to
    # mention the dropped key is the bug, not the fix.
    assert res.get("error") is not None or res.get("result", {}).get("isError") is True, payload
    assert "bogus" in payload
    # And nothing was executed.
    assert SIDE_EFFECT["writes"] == 0


def test_raw_wire_accepts_a_correct_call():
    """The guard must not break the happy path at the wire level either."""
    SIDE_EFFECT["writes"] = 0
    with _client() as c:
        sid = _session(c)
        _, res = _rpc(c, {"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {
            "name": "scoped_search",
            "arguments": {"query": "main", "project": "zhcorpus"}}}, sid)

    assert res.get("result", {}).get("isError") is not True, json.dumps(res)
    assert "zhcorpus" in json.dumps(res)
    assert SIDE_EFFECT["writes"] == 1


def test_raw_wire_tools_list_advertises_the_closed_contract():
    with _client() as c:
        sid = _session(c)
        _, res = _rpc(c, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, sid)
    tools = res["result"]["tools"]
    scoped = [t for t in tools if t["name"] == "scoped_search"][0]
    assert scoped["inputSchema"]["additionalProperties"] is False
