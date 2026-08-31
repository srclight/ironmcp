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

# reconnect_hint names how THIS server reports its running revision, so the stale-server
# diagnosis in a refusal points somewhere real. Optional; a generic default is used if omitted.
mcp = StrictArgsMCP("myserver", reconnect_hint="call the status tool to see the running revision")

@mcp.tool()
def search(query: str, project: str | None = None) -> dict: ...

attach_healthz(mcp, name="myserver")     # session-free GET /healthz, opt-in

# In the DEPLOYED entry point only — the library default stays permissive so tests are unaffected:
require_token_or_exit(os.environ.get("MYSERVER_TOKEN"), transport="streamable-http", service="myserver")
app = mcp.streamable_http_app()
app.add_middleware(bearer_middleware(os.environ["MYSERVER_TOKEN"]))
```

Pin one test that the guard is actually live (one line; replaces the hand-written conformance test every consumer used to copy):

```python
from mcpkit import assert_enforces

def test_every_tool_is_guarded():
    assert_enforces(mcp)     # raises if any tool advertises a contract the runtime does not keep
```

## What it provides

| | |
|---|---|
| `StrictArgsMCP` | refuses unknown args (`ToolError`) **and** stamps `additionalProperties: false` on advertised schemas — both halves, because runtime-only leaves the catalog lying. A tool that declares `additionalProperties: true` has opted OUT (a passthrough accepting arbitrary keys) and is honoured, not overridden. `reconnect_hint=` sets the per-server stale diagnosis |
| `assert_enforces(mcp)` | one-call conformance check for a test suite: asserts **advertisement == runtime** for every tool, and is proven to *fire* against a bare FastMCP. `aassert_enforces` is the async form |
| `code_sha()` | revision stamped once at import; `None` is honest. A long-lived daemon serves the code it launched with |
| `attach_healthz()` | **session-free** GET endpoint reporting `code_sha` and `mcpkit_version`. A health check inside the MCP session cannot report that the session is the broken thing |
| `bearer_middleware()` | constant-time bearer check with `WWW-Authenticate: Bearer` on the 401; `/healthz` exempt so a restart script can verify without a credential |
| `require_token_or_exit()` | fail-closed on the deployed path, exit **78** (`EX_CONFIG`) to pair with systemd `RestartPreventExitStatus=78` |

## For AI agents calling a guarded server

If a tool call comes back with **`unknown argument(s): … running older code than you think`**, the arguments you sent are not wrong in general — this *particular server process* does not implement them. A long-lived MCP daemon serves the code it was launched with, so a field added since it started is unknown to it. **Nothing ran and no result was computed.** Check the server's reported revision (the `reconnect_hint` in the message names how) and ask the user to reconnect the MCP; do not retry with the same arguments against the same process. Refusal is deliberate: bare FastMCP would have dropped the field silently and answered a question you did not ask.

## Adopting it (vendor, don't depend — yet)

mcpkit is not on PyPI. A consumer **vendors** one self-contained file and imports from it, so public and private repos adopt the same policy identically and no repo gains an unresolvable dependency:

```bash
python -m mcpkit.vendor --out path/to/_mcpkit.py    # generate the single-file build
python -m mcpkit.vendor --check path/to/_mcpkit.py  # verify it is unmodified, untampered, current
python -m mcpkit.vendor --audit                     # verify EVERY copy in consumers.txt (add yours!)
```

The generated file carries a whole-file hash, a separate **policy hash**, its version and upstream sha, so a hand-edited or stale copy is caught mechanically. An unlisted copy is invisible to `--audit` — add your path to `consumers.txt` when you vendor.

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
