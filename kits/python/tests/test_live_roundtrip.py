"""Live round-trip conformance: ADVERTISEMENT == RUNTIME proven over the REAL transport.

Pure guard-logic unit tests are not enough — the Dart kit shipped a bug that only appeared
once a real client drove ``tools/call`` through the full server pipeline (middleware runs
there; ``MCPServer.call_tool`` bypasses it). So every assertion here goes through a genuine
``ClientSession`` <-> low-level server pair over in-memory streams, the same path a networked
client takes.

One session, one hardened server, one tool with a declared object schema, both paths:
  (a) VALID args           -> the tool actually RUNS and returns its computed result;
  (b) an UNDECLARED extra  -> the call is REFUSED and the response says so (is_error + prose).

``aassert_enforces_v2`` is exercised alongside as the transport-level refuse invariant. It
deliberately does NOT execute tools for an accept-path probe (executing an arbitrary
zero-arg tool on someone's server could restart/quit it); the accept path is proven here
with a known-safe tool instead.
"""

from __future__ import annotations

import anyio
import pytest
from mcp.client.session import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

from ironmcp.conformance import PROBE_KEY, aassert_enforces_v2
from tests.harness import build_strict_server, result_text


async def _drive_round_trip(server):
    """Open ONE real client<->server session and return the observations to assert on.

    Returns a dict capturing: the advertised additionalProperties for ``echo``, the valid
    call's (is_error, text), and the extra-arg call's (is_error, text, structured_content).
    """
    obs: dict = {}
    ll = server._lowlevel_server
    async with create_client_server_memory_streams() as ((cr, cw), (sr, sw)):
        async with anyio.create_task_group() as tg:
            tg.start_soon(lambda: ll.run(sr, sw, ll.create_initialization_options()))
            async with ClientSession(cr, cw) as client:
                await client.initialize()

                # --- advertisement: the catalog tells an agent extras are refused ---
                tools = (await client.list_tools()).tools
                echo = next(t for t in tools if t.name == "echo")
                obs["advertised_additional_properties"] = echo.input_schema.get(
                    "additionalProperties"
                )

                # --- (a) valid args: the tool RUNS and returns its result ---
                ok = await client.call_tool("echo", {"a": "x", "b": "y"})
                obs["valid_is_error"] = bool(getattr(ok, "is_error", False))
                obs["valid_text"] = result_text(ok)

                # --- (b) undeclared extra arg: the call is REFUSED ---
                bad = await client.call_tool("echo", {"a": "x", "surprise": 1})
                obs["extra_is_error"] = bool(getattr(bad, "is_error", False))
                obs["extra_text"] = result_text(bad)
                obs["extra_structured"] = getattr(bad, "structured_content", None)
            tg.cancel_scope.cancel()
    return obs


@pytest.mark.asyncio
async def test_hardened_server_round_trip_accepts_valid_and_refuses_extra():
    """A CLIENT drives tools/call over the real transport against a HARDENED server:
    valid args run the tool and return its result; an undeclared extra arg is refused."""
    obs = await _drive_round_trip(build_strict_server())

    # Advertisement matches the runtime the client is about to experience.
    assert obs["advertised_additional_properties"] is False

    # (a) Accept path: the tool ran end-to-end and returned the value it computed.
    assert obs["valid_is_error"] is False
    assert "x|y" in obs["valid_text"]

    # (b) Refuse path: the response is an error and names the offending key; the tool never ran.
    assert obs["extra_is_error"] is True
    assert "unknown argument(s): surprise" in obs["extra_text"]
    assert "Nothing was executed" in obs["extra_text"]
    # Machine-readable twin of the prose, so an agent parses rather than scrapes.
    assert obs["extra_structured"]["ironmcp"]["unknown"] == ["surprise"]
    assert "surprise" not in obs["extra_structured"]["ironmcp"]["accepted"]


@pytest.mark.asyncio
async def test_conformance_runner_proves_the_refuse_invariant_over_the_transport():
    """The shared conformance runner drives a real tools/call per closed tool and asserts
    the unknown-argument probe is refused — the same transport path, not an introspection.
    It returns the count of tools it actually exercised."""
    n = await aassert_enforces_v2(build_strict_server())
    assert n >= 1


@pytest.mark.asyncio
async def test_probe_key_is_genuinely_undeclared_so_the_refusal_is_real():
    """Guard against a vacuous refuse-path: PROBE_KEY must be a key the tool does NOT accept,
    otherwise the conformance runner would be 'refusing' a legitimate argument and proving
    nothing. Confirm the hardened echo tool refuses PROBE_KEY specifically."""
    obs = {}
    server = build_strict_server()
    ll = server._lowlevel_server
    async with create_client_server_memory_streams() as ((cr, cw), (sr, sw)):
        async with anyio.create_task_group() as tg:
            tg.start_soon(lambda: ll.run(sr, sw, ll.create_initialization_options()))
            async with ClientSession(cr, cw) as client:
                await client.initialize()
                tools = (await client.list_tools()).tools
                echo = next(t for t in tools if t.name == "echo")
                obs["accepted"] = set((echo.input_schema.get("properties") or {}).keys())
                r = await client.call_tool("echo", {PROBE_KEY: 1})
                obs["is_error"] = bool(getattr(r, "is_error", False))
            tg.cancel_scope.cancel()
    assert PROBE_KEY not in obs["accepted"]  # the probe is genuinely undeclared
    assert obs["is_error"] is True  # ...and refused over the real transport
