"""Refuse unknown tool arguments instead of silently discarding them.

WHY THIS EXISTS. Stock FastMCP drops keys that are not in the tool signature, and it does so
BEFORE the tool function is entered, so a check inside a tool body can never fire -- the key is
already gone. The advertised ``inputSchema`` also omits ``additionalProperties: false``, so nothing
at the protocol layer flags it either. The only seam that still sees the raw argument dict is
``call_tool``.

Measured on srclight, 2026-08-28, before the fix::

    search_symbols(query="main", project="zhcorpus")   -> 20 hits, all zhcorpus
    search_symbols(query="main", projects="zhcorpus")  -> 20 hits, ZERO zhcorpus
                                                          (19 bible, 1 bank-scraper)

One added letter. No error, identical hit count, identical shape, real symbols -- from repos the
caller never asked about. That is not a lossy call, it is a WRONG one: a genuine answer to a
question nobody asked, with no way for the caller to learn their constraint was ignored.

NOT A PYTHON PROBLEM. scarlight (TypeScript SDK, low-level Server path) hit the identical bug on
2026-08-27 -- its own comment records that the low-level path "validates the REQUEST ENVELOPE only;
inputSchema is never enforced". Argument validation is something every MCP server must supply for
itself, in any runtime.

BOTH HALVES ARE REQUIRED. Refusing at runtime while still advertising a permissive schema leaves
the catalog telling agents that extras are fine, so they keep sending them. ``StrictArgsMCP`` does
runtime refusal AND stamps ``additionalProperties: false`` onto the listed schema.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from .seams import verify_seams

# Checked once, at import. A missing seam must not degrade into silent non-enforcement.
verify_seams()

__all__ = ["StrictArgsMCP"]


class StrictArgsMCP(FastMCP):
    """A FastMCP that rejects unknown tool arguments and advertises that it does."""

    async def call_tool(self, name: str, arguments: dict[str, Any]):  # type: ignore[override]
        tool = self._tool_manager.get_tool(name)
        if tool is not None and isinstance(arguments, dict):
            params = tool.parameters or {}
            # ABSENT "properties" vs PRESENT-BUT-EMPTY are different facts, and conflating them
            # leaves a hole (found 2026-08-29 by exhaustive testing against a realistic server):
            #   * key ABSENT           -> the schema could not be introspected. Say nothing;
            #                             refusing everything would brick the tool, and a guard
            #                             that becomes a wall is worse than the bug it prevents.
            #   * key PRESENT, empty   -> FastMCP generated {"properties": {}} because the tool
            #                             genuinely takes NO arguments. Extras must be refused,
            #                             or a zero-parameter tool is the one place a typo still
            #                             slips through silently.
            if "properties" in params:
                accepted = set(params.get("properties") or {})
                unknown = sorted(k for k in arguments if k not in accepted)
                if unknown:
                    accepts = ", ".join(sorted(accepted)) if accepted else "(no arguments)"
                    raise ToolError(
                        f"unknown argument(s): {', '.join(unknown)}. "
                        f"Tool {name!r} accepts: {accepts}. "
                        "Nothing was executed and no result was computed. "
                        # The stale-server hint is load-bearing: whoever hits this has no other
                        # route to the conclusion, because the call looked fine and the tool
                        # exists. A long-lived daemon serves the code it launched with.
                        "If you expected these arguments to work, this server process is probably "
                        "running older code than you think - check the server's reported revision "
                        "and reconnect the MCP."
                    )
        return await super().call_tool(name, arguments)

    async def list_tools(self):  # type: ignore[override]
        """Advertise the closed contract the runtime actually enforces."""
        tools = await super().list_tools()
        for t in tools:
            schema = getattr(t, "inputSchema", None)
            # Only stamp object schemas that declare properties. Stamping a schema with no
            # properties would advertise "accepts nothing", contradicting the call_tool rule
            # above that treats an empty property set as unknown rather than closed.
            # Stamp whenever "properties" is present -- including when empty, because an empty
            # property set is now enforced as "accepts nothing" rather than "unknown".
            if isinstance(schema, dict) and schema.get("type") == "object" and "properties" in schema:
                schema.setdefault("additionalProperties", False)
        return tools
