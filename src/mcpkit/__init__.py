"""mcpkit - shared MCP server POLICY for the Loqu8/Srclight/Gig8 estate.

This package ships NO TOOLS, deliberately. It constrains how your tools behave; it does
not give you capabilities.

It spans two SDK generations, which cannot both load in one interpreter (mcp 2 removed
FastMCP). So every name is imported LAZILY: ``import mcpkit`` touches no SDK, and each
attribute pulls in its module only when accessed. The v2 policy lives in ``mcpkit.v2``
(needs ``mcp>=2``); the v1 policy lives in the top-level modules (need ``mcp<2``).

ADDITION RULE: a helper enters this package only once it is already copy-pasted into
THREE servers AND the copies have drifted. Not before.
"""

from __future__ import annotations

import importlib

__version__ = "0.2.1"

# name -> submodule it lives in (relative). Resolved lazily on first access.
_LAZY = {
    # v2 (mcp>=2): the ServerMiddleware policy
    "StrictArgsMiddleware": ".v2",
    "strict_server": ".v2",
    "assert_enforces_v2": ".v2",
    "aassert_enforces_v2": ".v2",
    # v1 (mcp<2): the FastMCP-subclass policy
    "StrictArgsMCP": ".strict",
    "assert_enforces": ".conformance",
    "aassert_enforces": ".conformance",
    "code_sha": ".build",
    "started_at": ".build",
    "uptime_s": ".build",
    "attach_healthz": ".ops",
    "bearer_middleware": ".ops",
    "require_token_or_exit": ".ops",
    "EX_CONFIG": ".ops",
    "SeamError": ".seams",
    "verify_seams": ".seams",
    "LAST_KNOWN_GOOD": ".seams",
}

__all__ = ["__version__", *_LAZY]


def __getattr__(name: str):
    mod = _LAZY.get(name)
    if mod is None:
        raise AttributeError(f"module 'mcpkit' has no attribute {name!r}")
    return getattr(importlib.import_module(mod, __name__), name)


def __dir__():
    return sorted(__all__)
