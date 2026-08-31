"""One shared conformance check for v2: ADVERTISEMENT == RUNTIME.

Not "additionalProperties is always false" -- that would fight a legitimate passthrough
tool that opts out with ``additionalProperties: true``. The invariant is: whatever the
catalog tells an agent about extra arguments, the runtime must actually do. It catches
BOTH failures this estate has shipped -- advertised-closed-but-runtime-open (the silent
discard) and advertised-open-but-runtime-refuses (its reverse).

Drives a REAL client<->server session (``call_tool``/``list_tools`` on MCPServer bypass
middleware, so they would prove nothing). Failures are captured inside the session and
re-raised after it closes, so the diagnosis is a plain ``AssertionError`` and not an
anyio ``ExceptionGroup``.
"""

from __future__ import annotations

from typing import Any

import anyio
from mcp.client.session import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

__all__ = ["assert_enforces_v2", "aassert_enforces_v2", "PROBE_KEY"]

# A key no real tool declares. Sent as the lone argument to prove the closed contract holds.
PROBE_KEY = "zz_ironmcp_conformance_probe_key"


async def aassert_enforces_v2(server: Any, *, probe_key: str = PROBE_KEY) -> int:
    """Assert ADVERTISEMENT == RUNTIME for every introspectable tool of ``server``.
    Returns the count actually exercised; raises AssertionError naming the first tool
    that lies."""
    ll = server._lowlevel_server
    enforced = 0
    error: str | None = None
    no_tools = False

    async with create_client_server_memory_streams() as ((cr, cw), (sr, sw)):
        async with anyio.create_task_group() as tg:
            tg.start_soon(lambda: ll.run(sr, sw, ll.create_initialization_options()))
            async with ClientSession(cr, cw) as client:
                await client.initialize()
                tools = (await client.list_tools()).tools
                if not tools:
                    no_tools = True
                for t in tools or []:
                    schema = t.input_schema
                    if not (
                        isinstance(schema, dict)
                        and schema.get("type") == "object"
                        and "properties" in schema
                    ):
                        continue  # uninstrospectable -> permissive by design
                    adv = schema.get("additionalProperties")
                    if adv is True:
                        continue  # declared open (passthrough) -> honoured, not a lie
                    if adv is not False:
                        error = (
                            f"{t.name}: advertised schema is neither closed "
                            "(additionalProperties:false) nor explicitly open (true). The catalog "
                            "is silent, so an agent is told extras are fine while the SDK would drop "
                            "them. Serve this tool through StrictArgsMiddleware."
                        )
                        break
                    result = await client.call_tool(t.name, {probe_key: 1})
                    if getattr(result, "is_error", False):
                        enforced += 1
                        continue
                    error = (
                        f"{t.name}: advertises additionalProperties:false but the call accepted the "
                        f"unknown argument {probe_key!r} instead of refusing it. The guarantee the "
                        "catalog makes to agents is not enforced at runtime -- the discarded-argument "
                        "bug, back again."
                    )
                    break
            tg.cancel_scope.cancel()

    if no_tools:
        raise AssertionError("assert_enforces: the server advertises no tools -- nothing was checked")
    if error is not None:
        raise AssertionError(error)
    if enforced == 0:
        raise AssertionError(
            "assert_enforces: no tool actually enforced a closed contract, so nothing was proven. "
            "A conformance check that verifies nothing is worse than none. Register at least one tool "
            "with arguments, or serve through StrictArgsMiddleware."
        )
    return enforced


def assert_enforces_v2(server: Any, *, probe_key: str = PROBE_KEY) -> int:
    """Synchronous wrapper -- call from OUTSIDE an event loop (an ordinary test body)."""
    return anyio.run(lambda: aassert_enforces_v2(server, probe_key=probe_key))
