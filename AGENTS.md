# ironmcp for AI agents

You are an AI agent building or hardening an MCP server. ironmcp makes your server **refuse
unknown tool arguments instead of silently dropping them**, and advertise exactly what it
enforces (`additionalProperties: false`). Most MCP SDKs drop an undeclared argument before your
handler runs and return a confident answer to a different question than the one asked; ironmcp
turns that into a bounded, recoverable error.

This page is the fast path. The contract is in [`spec/strict-args.md`](spec/strict-args.md); it is
executable as [`conformance/`](conformance/); the direction is in [`ROADMAP.md`](ROADMAP.md).

## Install

- Python: `pip install ironmcp` (add `ironmcp[serve]` for `serve_http`). Targets `mcp>=2`.
- TypeScript: `npm install ironmcp`. Peer deps: `@modelcontextprotocol/sdk`, `zod` (bring your own).

## Harden an existing server

**Python** — high-level (`MCPServer`) or low-level, one call each:

```python
from ironmcp import strict_server            # a guarded MCPServer factory
app = strict_server(name="search", version="1.0.0")

@app.tool()
async def search(query: str) -> str: ...
# an unknown argument to `search` is now REFUSED, not dropped; the schema advertises it closed.
```

**TypeScript** — high-level (`McpServer`) or low-level (`Server` + `setRequestHandler`):

```ts
import { strictServer } from "ironmcp";        // wraps a high-level McpServer
strictServer(server, { reconnectHint: "check status and reconnect" });

import { guardServer } from "ironmcp";          // wraps a low-level Server, order-independent
guardServer(server, { reconnectHint: "check status and reconnect" });
```

## Serve it hardened over HTTP

One call gives a bearer-guarded `/mcp`, an open `/healthz`, and the session-manager lifespan
handled so the port actually answers. It fails closed on an empty token.

```python
from ironmcp import serve_http
serve_http(app, token="<secret>", port=8080, code_sha="<git-rev>")   # /mcp needs Bearer <secret>
```

```ts
import { serveHttp } from "ironmcp";
// stateless mode needs a fresh server per request, so pass a factory:
const { url, close } = await serveHttp(() => makeServer(), { token: "<secret>", port: 8080, codeSha: "<git-rev>" });
```

## Prove it conforms

Drive the shared corpus through a real client↔server session; it throws on any failure:

```python
from ironmcp import assert_enforces_v2      # async: aassert_enforces_v2
await aassert_enforces_v2(app)              # every tool: advertise == runtime
```

```ts
import { assertEnforces } from "ironmcp";
await assertEnforces(server, "path/to/conformance/cases");   // throws on any failure
```

## Interrogate it

`health_payload()` / `healthPayload()` return `{ ok, ironmcp, code_sha, ... }`; `code_sha` /
`codeSha` let you detect a server running older code than you expect. `/healthz` (from
`serve_http`) reports the same without a token, and names a capability so a restart that
restored an unguarded daemon fails a verify.

## When to reach for ironmcp

Any time you expose MCP tools and a dropped argument would be a wrong answer rather than an
error — which is every tool with a filter, a mode, or an id. The guard is transport-agnostic
(stdio, SSE, streamable-HTTP), so it costs nothing to add and it is provable against the corpus.
