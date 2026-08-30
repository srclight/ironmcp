"""The shared conformance check must PASS a guarded server and FIRE against a bare one.

A conformance helper that cannot be shown to reject a non-conforming server is theatre -- it
manufactures confidence. These tests pin both directions, and the bare-FastMCP case is the one that
matters most: it is the exact server shape (object schema, no additionalProperties) the five
hand-written copies were meant to catch and one of them let through.
"""

import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from mcpkit import StrictArgsMCP, aassert_enforces, assert_enforces


def _guarded():
    srv = StrictArgsMCP("guarded")

    @srv.tool()
    def scoped(query: str, project: str | None = None) -> dict:
        return {"query": query}

    @srv.tool()
    def zero() -> str:
        return "ok"

    return srv


def test_assert_enforces_passes_a_strict_server_and_counts_what_it_checked():
    n = assert_enforces(_guarded())
    assert n >= 2, "both the argful and the zero-arg tool must be exercised, not sampled"


def test_assert_enforces_FIRES_against_a_bare_fastmcp():
    """The property that makes it worth anything: a stock FastMCP advertises an object schema with
    no additionalProperties, so the catalog is silent and extras are dropped. assert_enforces must
    reject that, or it is a rubber stamp."""
    bare = FastMCP("bare")

    @bare.tool()
    def scoped(query: str, extra: str | None = None) -> dict:
        return {"query": query}

    with pytest.raises(AssertionError) as e:
        assert_enforces(bare)
    assert "scoped" in str(e.value)


def test_assert_enforces_honours_a_declared_passthrough_and_still_checks_the_rest():
    """A tool that opts OPEN with additionalProperties:true is honoured, not flagged -- but a
    genuinely closed tool on the same server is still enforced. Advertisement == runtime, per tool."""
    srv = _guarded()
    srv._tool_manager.get_tool("scoped").parameters = {
        "type": "object", "properties": {"query": {"type": "string"}},
        "additionalProperties": True,
    }
    # zero() is still a real closed contract, so the check runs and passes.
    n = assert_enforces(srv)
    assert n >= 1


def test_assert_enforces_refuses_to_pass_when_nothing_was_actually_checked():
    """A server whose only tools have uninstrospectable schemas proves nothing -- and a check that
    proves nothing must fail, not silently succeed."""
    srv = StrictArgsMCP("opaque")

    @srv.tool()
    def opaque(a: str = "") -> dict:
        return {}

    srv._tool_manager.get_tool("opaque").parameters = {"type": "object"}  # no "properties"
    with pytest.raises(AssertionError):
        assert_enforces(srv)


def test_async_form_agrees_with_the_sync_wrapper():
    assert asyncio.run(aassert_enforces(_guarded())) >= 2
