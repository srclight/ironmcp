"""assert_enforces_v2 must REJECT a bare server (advertises no additionalProperties -->
a silent catalog) and PASS a strict one. A conformance check never watched to fire is theatre."""

import pytest

from ironmcp.conformance import aassert_enforces_v2
from tests.harness import build_probe_server, build_strict_server


@pytest.mark.asyncio
async def test_fires_against_bare_server():
    with pytest.raises(AssertionError):
        await aassert_enforces_v2(build_probe_server())


@pytest.mark.asyncio
async def test_fires_against_advertised_closed_but_silently_dropping():
    """The exact bug the checker exists to catch: a server that ADVERTISES
    additionalProperties:false (so an agent trusts the closed contract) but does NOT
    enforce it at runtime -- the discarded-argument bug, back again. Built by leaving
    StrictArgsMiddleware UNBOUND (server=None): its tools/list stamp still closes the
    advertised schema, but the tools/call enforce branch requires a bound server and is
    skipped, so the unknown argument is silently dropped. If the checker did not FAIL
    this, it would be a false pass in a shipped public assertion."""
    from mcp.server.mcpserver import MCPServer

    from ironmcp.strict import StrictArgsMiddleware

    liar = build_probe_server(
        MCPServer(name="liar", version="0.0.0", middleware=[StrictArgsMiddleware()])
    )
    with pytest.raises(AssertionError, match="discarded-argument bug"):
        await aassert_enforces_v2(liar)


@pytest.mark.asyncio
async def test_passes_strict_server():
    n = await aassert_enforces_v2(build_strict_server())
    assert n >= 1


@pytest.mark.asyncio
async def test_rejects_a_server_with_no_tools():
    """A server advertising ZERO tools proves nothing — the checker must raise, not pass."""
    from mcp.server.mcpserver import MCPServer

    with pytest.raises(AssertionError, match="no tools"):
        await aassert_enforces_v2(MCPServer(name="empty", version="0.0.0"))


@pytest.mark.asyncio
async def test_rejects_when_every_tool_opted_open_nothing_enforced():
    """If every tool declares additionalProperties:true, all are skipped and enforced==0 —
    a check that verifies nothing must raise, not silently pass."""
    srv = build_strict_server()
    for name in ("echo", "ping"):
        srv._tool_manager.get_tool(name).parameters["additionalProperties"] = True
    with pytest.raises(AssertionError, match="nothing was proven"):
        await aassert_enforces_v2(srv)


def test_sync_wrapper_runs_outside_an_event_loop():
    """The public synchronous entry point (anyio.run under the hood) is callable from an
    ordinary, non-async test body and returns the enforced count."""
    from ironmcp.conformance import assert_enforces_v2

    assert assert_enforces_v2(build_strict_server()) >= 1
