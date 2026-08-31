"""Task 0 spike — reproduce the verified v2 SDK contract (mcp==2.1.1).

Run inside .venv-v2:  python spikes/v2_probe.py
Proves, end to end, the facts recorded in docs/v2-contract.md:
  * middleware attaches via the `middleware=[...]` constructor kwarg
  * a ServerMiddleware may SHORT-CIRCUIT a tools/call (return a CallToolResult
    without calling call_next) and the tool handler never runs
  * MCPServer.call_tool() BYPASSES middleware, so tests must drive a real
    client<->server session over memory streams
  * result flag is `is_error`; tool schema attr is `input_schema`
"""

from __future__ import annotations

import anyio
from mcp.client.session import ClientSession
from mcp.server.context import ServerMiddleware
from mcp.server.mcpserver import MCPServer
from mcp.shared.memory import create_client_server_memory_streams
from mcp.types import CallToolResult, TextContent

_RAN = {"echo": False}


class _RefuseTypo(ServerMiddleware):
    async def __call__(self, ctx, call_next):
        if getattr(ctx, "method", None) == "tools/call" and ctx.params:
            args = ctx.params.get("arguments") or {}
            if "typo" in args:
                return CallToolResult(
                    is_error=True,
                    content=[TextContent(type="text", text="REFUSED_typo")],
                )
        return await call_next(ctx)


def _build():
    srv = MCPServer(name="probe", version="0.0.0", middleware=[_RefuseTypo()])

    @srv.tool()
    async def echo(a: str) -> str:
        _RAN["echo"] = True
        return a

    return srv


async def _session_call(server, tool, arguments):
    ll = server._lowlevel_server
    async with create_client_server_memory_streams() as ((cr, cw), (sr, sw)):
        async with anyio.create_task_group() as tg:
            tg.start_soon(lambda: ll.run(sr, sw, ll.create_initialization_options()))
            async with ClientSession(cr, cw) as client:
                await client.initialize()
                result = await client.call_tool(tool, arguments)
            tg.cancel_scope.cancel()
    return result


async def main() -> None:
    # 1. call_tool bypasses middleware (the tool runs, no refusal)
    srv = _build()
    _RAN["echo"] = False
    direct = await srv.call_tool("echo", {"a": "x", "typo": 1})
    assert _RAN["echo"] is True, "expected call_tool to bypass middleware and run the tool"
    print("OK  call_tool bypasses middleware (is_error=%s)" % getattr(direct, "is_error", None))

    # 2. through a real session the middleware fires and short-circuits
    srv = _build()
    _RAN["echo"] = False
    bad = await _session_call(srv, "echo", {"a": "x", "typo": 1})
    assert bad.is_error is True and _RAN["echo"] is False, "short-circuit must skip the handler"
    print("OK  short-circuit via session: is_error=%s text=%s" % (bad.is_error, [c.text for c in bad.content]))

    srv = _build()
    good = await _session_call(srv, "echo", {"a": "x"})
    assert good.is_error is False
    print("OK  good call passes: is_error=%s text=%s" % (good.is_error, [c.text for c in good.content]))
    print("short-circuit OK")


if __name__ == "__main__":
    anyio.run(main)
