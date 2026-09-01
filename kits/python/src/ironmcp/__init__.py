"""ironmcp - the hardening & conformance standard for MCP servers (Python kit).

The strict-args guarantee as an MCP v2 ``ServerMiddleware`` (refuse unknown tool
arguments instead of silently dropping them; advertise exactly what you enforce), plus
the conformance corpus, agent-interrogable health, and fail-closed bearer auth. Targets
``mcp>=2``. The behavioural contract is in ``spec/``; it is executable as ``conformance/``.
"""

from __future__ import annotations

from .auth import HostGuard, make_bearer_asgi, make_host_guard_asgi
from .conformance import aassert_enforces_v2, assert_enforces_v2
from .corpus import Result, run_corpus
from .health import code_sha, health_payload
from .http import build_http_app, serve_http
from .quit import CleanQuit, reply_then_quit
from .readiness import (
    DataFileStatus,
    FeatureReadiness,
    LibraryStatus,
    ReadinessReport,
    ReadinessStatus,
)
from .registry import IronMcpEntry, IronMcpRegistry
from .results import MIN_BYTES, Results
from .serve import PortRetry
from .strict import StrictArgsMiddleware, strict_server

__version__ = "0.6.0"
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
    "make_host_guard_asgi",
    "HostGuard",
    "build_http_app",
    "serve_http",
    # F2 results
    "Results",
    "MIN_BYTES",
    # F3 serve port-retry
    "PortRetry",
    # F4 clean quit
    "CleanQuit",
    "reply_then_quit",
    # F5 registry
    "IronMcpEntry",
    "IronMcpRegistry",
    # F6 readiness
    "ReadinessStatus",
    "FeatureReadiness",
    "LibraryStatus",
    "DataFileStatus",
    "ReadinessReport",
]
