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
| PHP | `ironmcp` | Packagist | next | — |
| Rust | `ironmcp` | crates.io | planned | — |
| Go, Java/Kotlin, Swift | — | — | planned | — |
| C++, R, Perl | — | — | planned | — |

Every kit implements the same [`spec/strict-args.md`](spec/strict-args.md) and passes the same
[`conformance/`](conformance/) corpus. That is what makes "the same guarantee in every language"
provable rather than claimed.

## What has landed

- **The strict-args guard** — refuse unknown tool arguments at the pre-validation seam; stamp
  `additionalProperties: false` on every advertised tool. See [`spec/strict-args.md`](spec/strict-args.md).
  Python: `strict_server` / `StrictArgsMiddleware`. TypeScript: `strictServer` / `guardServer`.
- **The conformance corpus + runner** — [`conformance/cases/`](conformance/cases/) driven through
  a real in-memory client↔server session; `assert_enforces` / `assertEnforces`. A corpus never
  watched to FAIL against an unguarded server is theatre, so every kit also proves the bare server
  is refused. See [`conformance/README.md`](conformance/README.md).
- **Interrogable health** — `health_payload` / `healthPayload`, `code_sha` / `codeSha`, so an agent
  can tell when a server is running older code than it expects.
- **Fail-closed bearer auth** — `make_bearer_asgi` (Python) / `bearerOk` (TypeScript): no configured
  token authorises nothing; the comparison is constant-time.
- **`serve_http` / `serveHttp`** — a hardened, authenticated, health-checked streamable-HTTP daemon
  in one call: bearer-guarded `/mcp`, an open `/healthz` naming a capability, and the session-manager
  lifespan handled so the port actually answers.

## What is next

1. **The PHP kit** — WordPress, WooCommerce, Shopify, Laravel, Magento: the commerce and CMS backend
   of a large share of the web. Same core, same corpus, on the official PHP MCP SDK.
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
