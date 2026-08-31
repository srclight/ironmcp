"""ironmcp v2 — the strict-args guarantee as an MCP v2 ServerMiddleware.

Targets ``mcp>=2`` (MCPServer + ServerMiddleware). See ``docs/v2-contract.md`` for the
verified SDK contract this is built against.
"""

from __future__ import annotations

from .conformance import aassert_enforces_v2, assert_enforces_v2
from .corpus import Result, run_corpus
from .strict import StrictArgsMiddleware, strict_server

__all__ = [
    "StrictArgsMiddleware",
    "strict_server",
    "assert_enforces_v2",
    "aassert_enforces_v2",
    "run_corpus",
    "Result",
]
