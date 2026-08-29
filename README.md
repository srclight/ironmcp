# mcpkit

Shared MCP server **policy** for the Loqu8 / Srclight / Gig8 estate.

**It ships no tools, deliberately.** It constrains how your tools behave; it does not give you
capabilities. (`loqu8-dart`'s `McpServiceBase` is the opposite kind of base class — it inherits
apps working tools like screenshot and window control. Merging the two is how a shared library
becomes a framework nobody can change.)

## Why it exists

On 2026-08-28, six MCP servers were found to share one SDK default: FastMCP silently discards
unknown tool arguments *before* the tool function is entered. On srclight that produced confidently
wrong answers:

```
search_symbols(query="main", project="zhcorpus")    -> 20 hits, all zhcorpus
search_symbols(query="main", projects="zhcorpus")   -> 20 hits, ZERO zhcorpus
                                                       (19 bible, 1 bank-scraper)
```

One added letter. No error, identical hit count, identical shape, real symbols — from repos the
caller never asked about. Not a lossy call: a **wrong** one.

It is not a Python problem. scarlight (TypeScript SDK, low-level `Server` path) hit the identical
bug a day earlier. Argument validation is something every MCP server must supply for itself.

## Use

```python
from mcpkit import StrictArgsMCP, attach_healthz, bearer_middleware, require_token_or_exit

mcp = StrictArgsMCP("myserver")          # instead of FastMCP("myserver")

@mcp.tool()
def search(query: str, project: str | None = None) -> dict: ...

attach_healthz(mcp, name="myserver")     # session-free GET /healthz, opt-in

# In the DEPLOYED entry point only — the library default stays permissive so tests are unaffected:
require_token_or_exit(os.environ.get("MYSERVER_TOKEN"), transport="streamable-http", service="myserver")
app = mcp.streamable_http_app()
app.add_middleware(bearer_middleware(os.environ["MYSERVER_TOKEN"]))
```

## What it provides

| | |
|---|---|
| `StrictArgsMCP` | refuses unknown args (`ToolError`) **and** stamps `additionalProperties: false` on advertised schemas — both halves, because runtime-only leaves the catalog lying |
| `code_sha()` | revision stamped once at import; `None` is honest. A long-lived daemon serves the code it launched with |
| `attach_healthz()` | **session-free** GET endpoint. A health check inside the MCP session cannot report that the session is the broken thing |
| `bearer_middleware()` | constant-time bearer check, `/healthz` exempt so a restart script can verify without a credential |
| `require_token_or_exit()` | fail-closed on the deployed path, exit **78** (`EX_CONFIG`) to pair with systemd `RestartPreventExitStatus=78` |

## Deliberately excluded — the exclusions are the design

JSON-RPC/HTTP/SSE transport (FastMCP + Starlette already do it) · per-query timeouts (budgets are
per-server; a shared decorator makes timeout policy an estate-wide release) · typed absence /
`empty_reason` (the reasons are domain vocabulary) · tool registration · DI · logging · metrics ·
restart scripts · OAuth.

**Addition rule:** a helper enters this package only once it is already copy-pasted into **three**
servers *and* the copies have drifted.

## Tests

```bash
PYTHONPATH=src python -m pytest
```

The suite is built so it cannot pass without executing:

- **Execution sentinels** — a refused call asserts `entered == 0`, proving the body never ran. An
  error alone is not proof.
- **Schema-only tests are banned** — asserting `additionalProperties is False` without calling the
  tool is the discarded-argument bug in test form.
- **Raw-wire tests** send literal JSON-RPC, not SDK client calls, so what is asserted is what a
  caller receives.
- **`tests/conftest.py` fails the run on an unexplained skip.** A skip must name an issue URL. Three
  tests once reported green without running because a decorator was silently re-parented.
- `--strict-markers --strict-config`, `xfail_strict`, warnings-as-errors.

## Background

`Vault/Projects/mcp-chassis/` (research, external reviews, claim verification) ·
`Vault/Areas/AI Agents/agent-engineering-learnings.md` (the discipline) ·
`Vault/Areas/AI Agents/mcp-port-registry.md` (addresses).
