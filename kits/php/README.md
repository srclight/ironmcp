# ironmcp (PHP)

MCP servers that refuse unknown arguments instead of silently dropping them — advertisement == runtime.

_Part of the [ironmcp](../../README.md) monorepo — one contract, one [conformance corpus](../../conformance/), a native kit per language. For AI agents: [AGENTS.md](../../AGENTS.md). Direction: [ROADMAP.md](../../ROADMAP.md)._

The official PHP MCP SDK (`mcp/sdk`) already validates tool arguments against the JSON Schema
(via Opis), but reflection-generated schemas are left **open** (no `additionalProperties: false`),
so an undeclared argument passes validation and is silently dropped. On a WooCommerce order tool
or a Laravel command, that is a wrong action, silently. ironmcp closes every tool's schema and
adds a guard that **refuses** the unknown argument with a bounded, recoverable message — turning
the SDK's own dormant validator into an active one.

## Install

```sh
composer require ironmcp/core
```

Requires PHP `^8.1` and `mcp/sdk` `^0.8`. `ext-intl` is optional (enables NFKC-confusable
diagnosis in the refusal message; without it that one hint is skipped).

## Before and after

```php
use IronMcp\Harden;
use Mcp\Server;

$server = Harden::server(
    Server::builder()
        ->setServerInfo('search', '1.0.0')
        ->addTool([Tools::class, 'search']) // an undeclared arg to search would be dropped...
);
// ...now it is REFUSED: "unknown argument(s): projet. Tool 'search' accepts: query. Nothing was
// executed and no result was computed. ..." — and the tool schema advertises additionalProperties:false.

$server->run($transport);
```

`Harden::server()` adds the strict-args guard and stamps every tool schema closed. If you build
the registry yourself, `Harden::registry($registry)` is the post-build stamp primitive.

## Conformance

The behaviour is pinned by the language-neutral corpus shared with the Python and TypeScript kits
(see [`spec/strict-args.md`](../../spec/strict-args.md) and [`conformance/`](../../conformance/)).
`IronMcp\Corpus::assertEnforces($driver, $casesDir)` throws on any failure; a bare server FAILS
the corpus, which is how "advertise == runtime" stays provable rather than claimed.

## The refusal

A refusal is an `isError` tool result (not a protocol error): the prose message a human/agent
reads, plus machine-readable `structuredContent.ironmcp = { refused, tool, unknown[], accepted[] }`
so an agent parses which arguments were rejected. Values are never echoed — only key names.
