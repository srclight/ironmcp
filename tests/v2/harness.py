"""The v2 test harness — a real client<->server session over memory streams.

`MCPServer.call_tool()` bypasses middleware (verified, Task 0 / docs/v2-contract.md),
so it proves nothing about the guarantee an agent actually experiences. Every test
and the conformance runner drive a request the way a real client does: through the
full server pipeline, where middleware fires.
"""

from __future__ import annotations

from typing import Any

import anyio
from mcp.client.session import ClientSession
from mcp.server.mcpserver import MCPServer
from mcp.shared.memory import create_client_server_memory_streams


def build_probe_server(server: MCPServer | None = None) -> MCPServer:
    """A minimal server with a 2-arg tool and a no-arg tool. Reused across the suite."""
    srv = server or MCPServer(name="probe", version="0.0.0")

    @srv.tool()
    async def echo(a: str, b: str = "default") -> str:
        return f"{a}|{b}"

    @srv.tool()
    async def ping() -> str:
        return "pong"

    return srv


async def _in_session(server: MCPServer, fn):
    ll = server._lowlevel_server
    async with create_client_server_memory_streams() as ((cr, cw), (sr, sw)):
        async with anyio.create_task_group() as tg:
            tg.start_soon(lambda: ll.run(sr, sw, ll.create_initialization_options()))
            async with ClientSession(cr, cw) as client:
                await client.initialize()
                result = await fn(client)
            tg.cancel_scope.cancel()
    return result


async def session_call(server: MCPServer, tool: str, arguments: dict[str, Any]):
    """Call a tool through a real session; returns the CallToolResult (see .is_error / .content)."""
    return await _in_session(server, lambda c: c.call_tool(tool, arguments))


async def session_list_tools(server: MCPServer):
    """List tools through a real session; returns the list of advertised Tool objects."""
    result = await _in_session(server, lambda c: c.list_tools())
    return result.tools


def result_text(result) -> str:
    """Join the text of a CallToolResult's content blocks."""
    return " ".join(getattr(c, "text", "") for c in (result.content or []))
