"""Unknown tool arguments must be REFUSED, and the refusal must be provable.

These tests exist because the bug they guard is INVISIBLE at the call site: the call succeeds, the
shape is right, the answer is wrong. Nothing else in a suite would catch a regression.

Note the deliberate absence of pytest-asyncio: coroutines are driven with asyncio.run so the runner
cannot silently fail to drive them. An inert @pytest.mark.asyncio reported three tests green
without running on 2026-08-29; that class of failure is not allowed in this file.
"""

import asyncio

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from mcpkit import StrictArgsMCP


def _server():
    """A server whose tool RECORDS that it ran. The counter is the whole point."""
    srv = StrictArgsMCP("test")
    state = {"entered": 0}

    @srv.tool()
    def scoped_search(query: str, project: str | None = None, limit: int = 10) -> dict:
        # Mirrors the real shape: the filter is OPTIONAL, so dropping it silently widens the
        # search instead of failing. That is what made the original bug invisible.
        state["entered"] += 1
        return {"query": query, "project": project, "limit": limit}

    @srv.tool()
    def no_params() -> str:
        state["entered"] += 1
        return "ok"

    return srv, state


def test_known_arguments_still_work():
    # The guard must not become a tax on correct calls.
    srv, state = _server()
    res = asyncio.run(srv.call_tool("scoped_search", {"query": "main", "project": "zhcorpus"}))
    assert "zhcorpus" in str(res)
    assert state["entered"] == 1


def test_typo_on_filter_is_refused_AND_body_never_runs():
    """The execution sentinel. An error alone is not proof the mutation was avoided."""
    srv, state = _server()
    with pytest.raises(ToolError) as e:
        asyncio.run(srv.call_tool("scoped_search", {"query": "main", "projects": "zhcorpus"}))
    msg = str(e.value)
    assert "projects" in msg                # names the offending key
    assert "project" in msg                 # shows what was accepted
    assert "Nothing was executed" in msg    # states no result was computed
    # PROOF the business logic was never entered. Without this the test passes even if the
    # tool ran and then something else raised.
    assert state["entered"] == 0


def test_every_unknown_key_is_reported_not_just_the_first():
    srv, _ = _server()
    with pytest.raises(ToolError) as e:
        asyncio.run(srv.call_tool("scoped_search", {"query": "x", "aaa": 1, "zzz": 2}))
    assert "aaa" in str(e.value) and "zzz" in str(e.value)


def test_error_names_the_stale_server_diagnosis():
    # Whoever hits this has no other route to the conclusion: the call looked fine and the tool
    # exists. If this hint is dropped, the error stops being actionable.
    srv, _ = _server()
    with pytest.raises(ToolError) as e:
        asyncio.run(srv.call_tool("scoped_search", {"query": "x", "bogus": 1}))
    low = str(e.value).lower()
    assert "revision" in low and "reconnect" in low


def test_zero_parameter_tool_is_not_bricked():
    """Empty property set means 'schema unknown', NOT 'accepts nothing'.

    A guard that becomes a wall is worse than the bug it prevents.
    """
    srv, state = _server()
    res = asyncio.run(srv.call_tool("no_params", {}))
    assert "ok" in str(res)
    assert state["entered"] == 1


def test_advertised_schema_declares_the_closed_contract():
    """Runtime refusal alone leaves the catalog lying by omission.

    srclight shipped only the runtime half on 2026-08-28; all 42 of its tools kept advertising
    permissive schemas, so agents were still told extras were fine.
    """
    srv, _ = _server()
    tools = {t.name: t for t in asyncio.run(srv.list_tools())}
    assert tools["scoped_search"].inputSchema.get("additionalProperties") is False


def test_zero_parameter_tool_schema_is_NOT_stamped():
    # Stamping a property-less schema would advertise "accepts nothing", contradicting the
    # runtime rule that treats an empty property set as unknown.
    srv, _ = _server()
    tools = {t.name: t for t in asyncio.run(srv.list_tools())}
    assert "additionalProperties" not in tools["no_params"].inputSchema


def test_schema_claim_matches_runtime_behaviour():
    """Ban on schema-only tests, enforced: assert the ADVERTISEMENT and the BEHAVIOUR agree.

    A test that inspects the schema and never calls the tool is the discarded-argument bug in
    test form -- a declaration the harness believes.
    """
    srv, state = _server()
    tools = {t.name: t for t in asyncio.run(srv.list_tools())}
    assert tools["scoped_search"].inputSchema["additionalProperties"] is False
    with pytest.raises(ToolError):
        asyncio.run(srv.call_tool("scoped_search", {"query": "x", "extra": 1}))
    assert state["entered"] == 0
