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

import unicodedata
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
                    raise ToolError(_unknown_args_message(name, unknown, accepted))
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


# The error message's SIZE is bounded by the server, never by its input. A caller sending 5,000
# unknown keys must not be able to reflect a 59kB error back over MCP and into the log
# (canes-fideles-d8, 2026-08-30). Values are NEVER echoed, only key NAMES — a rejected argument
# cannot be used to bounce data into logs, and that is deliberate, not incidental.
_MAX_ENUMERATED = 10


def _unknown_args_message(name: str, unknown: list[str], accepted: set[str]) -> str:
    shown = unknown[:_MAX_ENUMERATED]
    more = len(unknown) - len(shown)
    listed = ", ".join(shown) + (f", and {more} more" if more > 0 else "")
    accepts = ", ".join(sorted(accepted)) if accepted else "(no arguments)"

    # NFKC confusables. Python normalises identifiers at PARSE time, so a parameter written with
    # U+00B5 MICRO SIGN is advertised as U+03BC GREEK MU — two glyphs identical in nearly every
    # font. A developer copying the name from source is refused by something that looks exactly
    # like what they were told to send. Diagnose it by naming the CODEPOINT, since whoever hits
    # this has no other route to the answer. THE SCHEMA IS AUTHORITATIVE FOR ARGUMENT NAMES,
    # NEVER THE SOURCE, because normalisation happens between them.
    hints = []
    norm_accepted = {unicodedata.normalize("NFKC", a): a for a in accepted}
    for k in shown:
        canon = unicodedata.normalize("NFKC", k)
        if canon != k and canon in norm_accepted:
            cps = " ".join(f"U+{ord(c):04X}" for c in k)
            hints.append(f"{k!r} ({cps}) normalises to {norm_accepted[canon]!r}, which IS accepted")

    parts = [
        f"unknown argument(s): {listed}.",
        f"Tool {name!r} accepts: {accepts}.",
        "Nothing was executed and no result was computed.",
    ]
    if hints:
        parts.append("Note: " + "; ".join(hints) + ".")
    parts.append(
        "If you expected these arguments to work, this server process is probably running older "
        "code than you think - check the server's reported revision and reconnect the MCP."
    )
    return " ".join(parts)
