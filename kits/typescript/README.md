# ironmcp

_Part of the [ironmcp](../../README.md) monorepo — one contract, one [conformance corpus](../../conformance/), a native kit per language. For AI agents: [AGENTS.md](../../AGENTS.md). Direction: [ROADMAP.md](../../ROADMAP.md)._

MCP servers that refuse unknown arguments instead of silently dropping them — advertisement == runtime.

Most MCP SDKs validate a tool call against its declared parameters and **silently drop** any
argument that was not declared. One added letter (`project` → `projects`) yields a confident
answer to a question nobody asked, with no way for the caller to learn their constraint was
ignored. The official TypeScript SDK does this today: it strips unknown arguments before the
handler runs, and on the zero-argument case does not even advertise a closed schema. ironmcp
makes the server **refuse** the unknown argument with a bounded, recoverable message, and
**advertise exactly what it enforces** (`additionalProperties: false`) on every tool.

## Install

```sh
npm install ironmcp
```

`@modelcontextprotocol/sdk` and `zod` are peer dependencies — bring the versions your server
already uses; ironmcp never bundles them.

## Before and after

```ts
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { strictServer } from "ironmcp";
import { z } from "zod";

const server = new McpServer({ name: "search", version: "1.0.0" });
server.registerTool("search", { inputSchema: { query: z.string() } }, run);

// Without ironmcp: callTool("search", { query: "x", projet: "typo" })
//   -> the SDK drops `projet`, runs search("x"), returns a confident wrong answer.

strictServer(server, { reconnectHint: "check status and reconnect" });

// With ironmcp: the same call comes back as an error:
//   unknown argument(s): projet. Tool 'search' accepts: query.
//   Nothing was executed and no result was computed. If you expected these arguments to
//   work, this server process is probably running older code than you think - check status
//   and reconnect.
```

## Low-level servers

If you build on the low-level `Server` and register handlers with `setRequestHandler`
(as, for example, scarlight does), wrap it once — order does not matter:

```ts
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { guardServer } from "ironmcp";

const server = new Server({ name: "scarlight", version: "3.0.0" }, { capabilities: { tools: {} } });
guardServer(server, { reconnectHint: "check status -> server.revision and reconnect" });
// register your ListTools + CallTool handlers as usual; guardServer wraps them at the wire.
```

`guardCallTool` and `guardListTools` are exported too if you want to compose the guard onto
specific handlers yourself.

## Conformance

The behaviour is pinned by a language-neutral corpus shared with every other ironmcp kit
(see [`spec/strict-args.md`](../../spec/strict-args.md) and
[`conformance/`](../../conformance/)). A server conforms when it passes every case:

```ts
import { assertEnforces } from "ironmcp";
const passed = await assertEnforces(server, "path/to/conformance/cases"); // throws on any failure
```

The kit's own tests also watch the corpus FAIL against an unguarded server — a corpus never
watched to fail proves nothing.

## What else is in the box

- `checkUnknownArgs(schema, args)` / `stampClosed(schema)` — the pure 3-state rule, no SDK
  import, if you want the primitive without the adapter.
- `healthPayload()` / `codeSha()` — an interrogable health surface so an agent can tell when a
  server is running older code than it expects.
- `bearerOk(header, token)` — a fail-closed, constant-time bearer check for HTTP transports.
