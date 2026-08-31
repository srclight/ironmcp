"""One shared conformance check, so five hand-written copies cannot drift into six.

WHY THIS EXISTS. Every consumer that adopted StrictArgsMCP also hand-wrote an "all tools are
closed" test -- srclight, conductor, model-radar, zhcorpus, caneslight: five copies of one
assertion. They ALREADY diverged (caneslight's asserted different refusal wording), which is this
package's own addition rule met exactly: three copies AND drifted. So the check moves here and each
consumer calls it in one line.

WHAT IT PINS, and why it is the RIGHT invariant. Not "additionalProperties always becomes false" --
that would cement the two-state model and fight a legitimate passthrough tool that opts out with
``additionalProperties: true``. The invariant is ADVERTISEMENT == RUNTIME: whatever the catalog
tells an agent about extra arguments, the runtime must actually do. That single property catches
BOTH failures this estate shipped -- advertised-closed-but-runtime-open (the original silent-discard
bug) and advertised-open-but-runtime-refuses (its reverse) -- and both StrictArgsMCP and any future
opt-out-aware design satisfy it.

PROVEN TO FIRE. A conformance check that never fails is theatre. ``assert_enforces`` raises against a
bare FastMCP (whose object-with-properties tools advertise NO additionalProperties -- neither closed
nor explicitly open), and ``test_conformance.py`` pins exactly that. A check you have not watched
reject a non-conforming server is a check you cannot trust.
"""

from __future__ import annotations

import asyncio
from typing import Any

__all__ = ["assert_enforces", "aassert_enforces"]

# A key no real tool declares. Sent as the lone argument to prove the closed contract is enforced.
_PROBE_KEY = "zz_mcpkit_conformance_probe_key"


async def aassert_enforces(mcp: Any, *, probe_key: str = _PROBE_KEY) -> int:
    """Assert ADVERTISEMENT == RUNTIME for every introspectable tool. Returns the count actually
    exercised. Raises AssertionError naming the first tool that lies. Async form; see the sync
    ``assert_enforces`` wrapper for use inside a normal test."""
    tools = await mcp.list_tools()
    if not tools:
        raise AssertionError("assert_enforces: the server advertises no tools -- nothing was checked")

    enforced = 0
    for t in tools:
        schema = getattr(t, "inputSchema", None)
        if not (isinstance(schema, dict) and schema.get("type") == "object" and "properties" in schema):
            # Uninstrospectable schema -> permissive by design; there is no closed contract to hold.
            continue

        adv = schema.get("additionalProperties")
        if adv is True:
            # The author opted the tool OPEN (a passthrough/proxy accepting arbitrary keys). That is
            # a declared, honoured contract, not a lie -- leave it be.
            continue
        if adv is not False:
            raise AssertionError(
                f"{t.name}: advertised schema is neither closed (additionalProperties:false) nor "
                "explicitly open (true). The catalog is silent, so an agent is told extras are fine "
                "while stock FastMCP would drop them -- the exact silent-discard this guard exists "
                "to close. Serve this tool through StrictArgsMCP."
            )

        # adv is False: the catalog promises extras are refused, so the runtime MUST refuse them.
        try:
            await mcp.call_tool(t.name, {probe_key: 1})
        except Exception:
            enforced += 1
            continue
        raise AssertionError(
            f"{t.name}: advertises additionalProperties:false but call_tool accepted the unknown "
            f"argument {probe_key!r} instead of refusing it. The guarantee the catalog makes to "
            "agents is not enforced at runtime -- the discarded-argument bug, back again."
        )

    if enforced == 0:
        raise AssertionError(
            "assert_enforces: no tool actually enforced a closed contract, so nothing was proven. "
            "A conformance check that verifies nothing is worse than none -- it manufactures "
            "confidence. Register at least one tool with arguments, or serve through StrictArgsMCP."
        )
    return enforced


def assert_enforces(mcp: Any, *, probe_key: str = _PROBE_KEY) -> int:
    """Synchronous wrapper for ``aassert_enforces`` -- drives the coroutine with ``asyncio.run`` so a
    plain test needs no async runner. Call from OUTSIDE an event loop (an ordinary test body)."""
    return asyncio.run(aassert_enforces(mcp, probe_key=probe_key))
