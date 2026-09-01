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
