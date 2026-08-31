"""ironmcp v2 — the strict-args guarantee as an MCP v2 ServerMiddleware.

Targets ``mcp>=2`` (MCPServer + ServerMiddleware). See ``docs/v2-contract.md`` for the
verified SDK contract this is built against.
"""

from __future__ import annotations

from .auth import make_bearer_asgi
from .conformance import aassert_enforces_v2, assert_enforces_v2
from .corpus import Result, run_corpus
from .health import code_sha, health_payload
from .strict import StrictArgsMiddleware, strict_server

__all__ = [
    "StrictArgsMiddleware",
    "strict_server",
    "assert_enforces_v2",
    "aassert_enforces_v2",
    "run_corpus",
    "Result",
    "code_sha",
    "health_payload",
    "make_bearer_asgi",
]
