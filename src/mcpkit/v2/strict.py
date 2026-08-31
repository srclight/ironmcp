"""Refuse unknown tool arguments in MCP v2, instead of silently discarding them.

The v1 kit subclassed ``FastMCP`` and overrode ``call_tool``. MCP v2 has no FastMCP;
it has a first-class ``ServerMiddleware`` that runs BEFORE argument validation -- the
seam where an unknown key is still visible before the SDK (like v1) drops it. So the
policy becomes a middleware you attach, not a base class you inherit.

``MCPServer.call_tool()`` bypasses middleware; only the transport request path invokes
it. Build servers with :func:`strict_server` (or attach :class:`StrictArgsMiddleware`
via the ``middleware=`` kwarg and bind the server) so the guarantee reaches real clients.
See ``docs/v2-contract.md``.
"""

from __future__ import annotations

from typing import Any

from mcp.server.context import ServerMiddleware
from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, TextContent

from ._messages import _DEFAULT_RECONNECT_HINT, unknown_args_message

__all__ = ["StrictArgsMiddleware", "strict_server"]


class StrictArgsMiddleware(ServerMiddleware):
    """Rejects unknown tool arguments at the pre-validation seam; never drops them.

    Bind the server it guards either by passing it in, or via :func:`strict_server`
    which wires the construction-order for you.
    """

    def __init__(self, server: MCPServer | None = None, *, reconnect_hint: str | None = None) -> None:
        self._server = server
        self._reconnect_hint = reconnect_hint or _DEFAULT_RECONNECT_HINT

    async def __call__(self, ctx, call_next):
        if getattr(ctx, "method", None) == "tools/call" and ctx.params and self._server is not None:
            name = ctx.params.get("name")
            arguments = ctx.params.get("arguments") or {}
            tool = self._server._tool_manager.get_tool(name) if name else None
            schema = getattr(tool, "parameters", None)
            # Three facts about a schema, each with a different answer (verbatim from v1):
            #   * "properties" ABSENT           -> uninstrospectable; stay permissive.
            #   * "properties" PRESENT (even {}) -> refuse extras (a zero-arg tool included).
            #   * additionalProperties is True  -> the author OPTED OUT (passthrough); honour it.
            if (
                isinstance(schema, dict)
                and "properties" in schema
                and schema.get("additionalProperties") is not True
                and isinstance(arguments, dict)
            ):
                accepted = set(schema.get("properties") or {})
                unknown = sorted(k for k in arguments if k not in accepted)
                if unknown:
                    msg = unknown_args_message(name, unknown, accepted, self._reconnect_hint)
                    # Short-circuit: return the refusal WITHOUT calling call_next, so the
                    # tool handler never runs (verified legal, docs/v2-contract.md).
                    return CallToolResult(
                        is_error=True, content=[TextContent(type="text", text=msg)]
                    )
        return await call_next(ctx)


def strict_server(
    *args: Any, reconnect_hint: str | None = None, **kwargs: Any
) -> MCPServer:
    """Build an ``MCPServer`` guarded by :class:`StrictArgsMiddleware`.

    Handles the construction-order wrinkle (the middleware needs a reference to the
    server it guards, but the server is built with the middleware list). Any
    ``middleware=`` passed in runs after the strict guard.
    """
    guard = StrictArgsMiddleware(reconnect_hint=reconnect_hint)
    extra = list(kwargs.pop("middleware", None) or [])
    server = MCPServer(*args, middleware=[guard, *extra], **kwargs)
    guard._server = server
    return server
