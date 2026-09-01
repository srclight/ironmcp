# ironmcp

_Part of the [ironmcp](../../README.md) monorepo — one contract, one [conformance corpus](../../conformance/), a native kit per language. For AI agents: [AGENTS.md](../../AGENTS.md). Direction: [ROADMAP.md](../../ROADMAP.md)._

**The hardening & conformance standard for MCP servers.** Dedicated, hardened,
conformant MCP tooling on every platform — so nobody hand-rolls JSON-RPC again.

`ironmcp` is a policy layer for [Model Context Protocol](https://modelcontextprotocol.io)
servers. It ships **no tools** — it constrains how *your* tools behave. The Python kit
targets `mcp>=2`.

## The problem it fixes

Most MCP SDKs **silently drop** any argument a tool doesn't declare, before the tool
runs — no error, no signal. One added letter (`project` → `projects`) yields a genuine
answer to a question nobody asked, with no way for the caller to learn their constraint
was ignored. `ironmcp` refuses the unknown argument instead, and advertises that it does.

## Quick start

```python
from ironmcp import strict_server

app = strict_server(name="my-server", version="1.0.0")

@app.tool()
async def search(query: str, limit: int = 20) -> str:
    ...
```

Now `search(query="x", projekt="y")` comes back as an **error result**
("unknown argument(s): projekt … Nothing was executed"), instead of silently running
with `projekt` dropped. The advertised schema carries `additionalProperties: false`, so
agents are told the truth — **advertisement == runtime**. A tool that sets
`additionalProperties: true` opts out and accepts arbitrary keys.

## Conformance — the guarantee is provable

```python
from ironmcp import aassert_enforces_v2, run_corpus

await aassert_enforces_v2(app)                         # every tool: advertisement == runtime
results = await run_corpus(app, "conformance/cases")   # the language-neutral corpus
assert all(r.passed for r in results)
```

The behavioural contract lives in [`spec/`](../../spec/), executable as
[`conformance/`](../../conformance/) — a JSON corpus owned by no language. A kit in *any*
language conforms when a server built with its strict layer passes the same cases. That
is what makes "the same guarantee everywhere" provable rather than claimed.

## Also included

- `health_payload(name, version)` / `code_sha()` — agent-interrogable liveness (an agent
  learns *what* a server is and *whether it is current* without asking a human).
- `make_bearer_asgi(app, expected_token=...)` — fail-closed bearer auth (401 +
  `WWW-Authenticate`) to wrap `app.streamable_http_app()`.

## API

`from ironmcp import` — `strict_server`, `StrictArgsMiddleware`, `assert_enforces_v2`,
`aassert_enforces_v2`, `run_corpus`, `Result`, `health_payload`, `code_sha`,
`make_bearer_asgi`.

See [`examples/demo.py`](examples/demo.py) for a runnable server that proves the
guarantee end to end.

## License

Apache-2.0. By [Srclight](https://srclight.dev).
