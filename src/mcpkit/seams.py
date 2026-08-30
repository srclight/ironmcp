"""Verify at import that the SDK seams this package depends on still exist.

WHY FAIL LOUDLY. ``StrictArgsMCP`` reaches into FastMCP internals -- ``_tool_manager``,
``Tool.parameters``, and an async ``call_tool`` to override. All three are private or unstable, and
python-sdk v2 is expected to move them.

If a seam disappears, the natural failure is the worst one available: the subclass still constructs,
still serves, and silently stops enforcing. That is precisely the family this estate has spent two
days cataloguing -- a declaration that no longer takes effect while everything reports success. A
server would advertise ``additionalProperties: false`` and accept extras.

So the seams are checked once at import and the failure is an exception naming what moved. Louder
than a wrong answer, and it happens at start-up rather than at the first mistyped argument.

ONE FastMCP, NOT TWO. These seams are the shapes of the FastMCP BUNDLED IN THE OFFICIAL ``mcp`` SDK
(``mcp.server.fastmcp``), pinned ``mcp>=1.28,<2``. They are NOT the shapes of the standalone
PrefectHQ ``fastmcp`` v3 package (which vaultlight runs) -- there ``get_tool`` is public, middleware
is first-class, and the internals mcpkit reaches into do not exist under these names. mcpkit does not
work on fastmcp v3 as-is; adopting it there is a rewrite, not a config change. Written down here so
nobody vendors this file into a v3 server and is surprised when the seam-check passes and enforcement
still does not fit.
"""

from __future__ import annotations

import inspect

LAST_KNOWN_GOOD = "mcp 1.28-1.x"

__all__ = ["verify_seams", "SeamError", "LAST_KNOWN_GOOD"]


class SeamError(RuntimeError):
    """A FastMCP internal that mcpkit depends on has moved or disappeared."""


def _sdk_version() -> str:
    try:
        from importlib.metadata import version
        return version("mcp")
    except Exception:
        return "unknown"


def verify_seams() -> None:
    from mcp.server.fastmcp import FastMCP

    missing: list[str] = []

    if not hasattr(FastMCP, "call_tool"):
        missing.append("FastMCP.call_tool (the override point)")
    elif not inspect.iscoroutinefunction(FastMCP.call_tool):
        # If it stops being async our override's signature is wrong and every call breaks --
        # noisy, but worth naming precisely rather than letting a TypeError surface at runtime.
        missing.append("FastMCP.call_tool is no longer a coroutine")

    if not hasattr(FastMCP, "list_tools"):
        missing.append("FastMCP.list_tools (schema stamping point)")

    try:
        from mcp.server.fastmcp.tools import ToolManager
        if not hasattr(ToolManager, "get_tool"):
            missing.append("ToolManager.get_tool")
    except Exception:
        missing.append("mcp.server.fastmcp.tools.ToolManager")

    try:
        from mcp.server.fastmcp.tools.base import Tool
        if "parameters" not in getattr(Tool, "model_fields", {}):
            missing.append("Tool.parameters (the advertised schema)")
    except Exception:
        missing.append("mcp.server.fastmcp.tools.base.Tool")

    if missing:
        raise SeamError(
            "mcpkit depends on FastMCP internals that have moved: "
            + "; ".join(missing)
            + f". Detected mcp version: {_sdk_version()}; last known good: {LAST_KNOWN_GOOD}. "
            "REFUSING TO IMPORT rather than silently serving without argument validation -- a "
            "server that advertises additionalProperties:false and then accepts extras is worse "
            "than one that never claimed to validate. Pin mcp<2 or update mcpkit."
        )
