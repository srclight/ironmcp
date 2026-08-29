"""mcpkit - shared MCP server POLICY for the Loqu8/Srclight/Gig8 estate.

This package ships NO TOOLS, deliberately. It constrains how your tools behave; it does not give
you capabilities. (loqu8-dart's McpServiceBase is the opposite kind of base class -- it inherits
apps working tools like screenshot and window control. Merging the two is how a shared library
becomes a framework nobody can change.)

DELIBERATELY EXCLUDED, and the exclusions are the design:
  * JSON-RPC / HTTP / SSE transport      -- FastMCP + Starlette already do this
  * per-query timeouts                   -- budgets are per-server; a shared decorator makes
                                            timeout policy a six-server release
  * typed absence / empty_reason         -- the reasons are domain vocabulary; a shared union is
                                            how this becomes a framework
  * tool registration, DI, logging, metrics, restart scripts, OAuth

ADDITION RULE: a helper enters this package only once it is already copy-pasted into THREE servers
AND the copies have drifted. Not before.
"""

from .build import code_sha, started_at, uptime_s
from .ops import EX_CONFIG, attach_healthz, bearer_middleware, require_token_or_exit
from .seams import LAST_KNOWN_GOOD, SeamError, verify_seams
from .strict import StrictArgsMCP

__version__ = "0.1.0"
__all__ = [
    "StrictArgsMCP",
    "code_sha", "started_at", "uptime_s",
    "attach_healthz", "bearer_middleware", "require_token_or_exit", "EX_CONFIG",
    "SeamError", "verify_seams", "LAST_KNOWN_GOOD",
]
