# ironmcp roadmap

ironmcp is the hardening and conformance standard for MCP servers: tool servers that refuse
unknown arguments instead of silently dropping them, and advertise exactly what they enforce.
One contract ([`spec/`](spec/)), one language-neutral corpus ([`conformance/`](conformance/)),
and a native kit per language — the way POSIX is one specification with a conformance suite and
many native libraries, not one library ported everywhere.

This file is the public technical direction. It says what is here, what is next, and how the
pieces fit, so a developer or an AI agent can find what they want quickly.

## Kits

| Kit | Package | Registry | Status | Location |
|-----|---------|----------|--------|----------|
| Python | `ironmcp` | PyPI | shipped | [`kits/python/`](kits/python/) |
| TypeScript | `ironmcp` | npm | shipped | [`kits/typescript/`](kits/typescript/) |
| PHP | `ironmcp/core` | Packagist | shipped | [`kits/php/`](kits/php/) |
| Dart | `ironmcp` | pub.dev | shipped | [`kits/dart/`](kits/dart/) |
| Rust | `ironmcp` | crates.io | next | — |
| Go, Java/Kotlin, Swift | — | — | planned | — |
| C++, R, Perl | — | — | planned | — |

Every kit implements the same [`spec/strict-args.md`](spec/strict-args.md) and passes the same
[`conformance/`](conformance/) corpus. That is what makes "the same guarantee in every language"
provable rather than claimed.

## What has landed

The full substrate, in **all four kits** (Python, TypeScript, PHP, Dart) from one dependency, proven by
the shared corpus:

- **The strict-args guard** — refuse unknown tool arguments; stamp `additionalProperties: false` so
  advertisement == runtime. Python `strict_server`, TypeScript `strictServer`/`guardServer`, PHP
  `Harden::server`, Dart `StrictMcpServer` (a drop-in `McpServer` subclass).
- **The conformance corpus + runner** — cases driven through a real client↔server session; every kit
  also proves the *bare* server FAILS, because a corpus never watched to fail is theatre.
- **Self-discovery registry** — a server registers itself; any agent enumerates every live ironmcp
  server (namespace, port, capabilities). The registry file format is **byte-identical across all four
  languages**, so servers in different languages appear in one shared list.
- **Structured readiness + health** — a full readiness report (feature / native-library / data-file
  status with a computed verdict that excludes environmental blocks) and a lightweight health tool;
  `code_sha` to detect a server running older code than expected.
- **Hardened serving** — a bearer-guarded `/mcp` (fail-closed, constant-time), an open `/healthz`
  naming capabilities, a **DNS-rebinding host guard on by default**, and Windows TIME_WAIT port-retry.
- **Content + clean-quit helpers** — correct image/binary tool results (with an empty-capture guard),
  and a fenced, ordered, idempotent shutdown scaffold with an honest `quit` tool an agent can call.

**Proven in production:** ironmcp hardens a desktop application's live MCP server (60+ tools) on both
Linux and Windows, with zero behaviour change — a mistyped argument that used to return a confident
wrong answer now returns a clear refusal.

## What is next

1. **The Rust kit** — same core, same corpus, on the Rust MCP SDK. (PHP shipped; its Laravel and
   WordPress adapters + a serve_http-PHP are the next PHP steps.)
2. **Retire the legacy SSE co-mount** across servers still launching `--transport sse` and standardise
   on streamable-HTTP (the SSE transport is deprecated in the MCP spec). Clients already use `/mcp`.
3. **`ironmcp inspect`** — a CLI that runs the conformance corpus against any running server and prints
   a verdict, so conformance is a one-command check.
4. **Upstream strict-args** — the official SDKs silently drop unknown arguments today (TypeScript SDK
   issues [#147](https://github.com/modelcontextprotocol/typescript-sdk/issues/147),
   [#2636](https://github.com/modelcontextprotocol/typescript-sdk/issues/2636)). Land the guarantee
   upstream so advertisement and runtime agree by default.
5. **The generator** — spec + corpus to a conforming kit in a new language, so a new kit is mostly
   generated and then hand-finished.

## The contract is the corpus

New behaviour enters ironmcp only with a case in [`conformance/cases/`](conformance/cases/) that pins
it. A guarantee with no case is not a guarantee. To change what ironmcp promises, add or change a case
first; every kit must then still pass. See [`conformance/README.md`](conformance/README.md).

## How to help

See [`CONTRIBUTING.md`](CONTRIBUTING.md) — including the recipe for adding a new language kit. The two
shipped kits are the worked examples.
