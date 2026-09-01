# ironmcp/core (PHP)

MCP servers that refuse unknown arguments instead of silently dropping them — advertisement == runtime.

> **This is a read-only mirror** of the PHP kit for Packagist. The source of truth, the other
> language kits, and the full docs live in the monorepo:
> **[github.com/srclight/ironmcp](https://github.com/srclight/ironmcp)** (see `kits/php/`).

```sh
composer require ironmcp/core
```

The official PHP MCP SDK (`mcp/sdk`) validates tool arguments via Opis but leaves reflection
schemas open, so an undeclared argument passes and is silently dropped. `IronMcp\Harden::server()`
closes every tool's schema and refuses the unknown argument with a bounded, recoverable message —
turning the SDK's own validator into an active guard. Same guarantee, same conformance corpus, as
the [Python](https://pypi.org/project/ironmcp/) and [TypeScript](https://www.npmjs.com/package/ironmcp) kits.

```php
use IronMcp\Harden;
use Mcp\Server;

$server = Harden::server(Server::builder()->setServerInfo('search', '1.0.0')->addTool([Tools::class, 'search']));
$server->run($transport); // an undeclared argument is now REFUSED, not dropped
```

See the [spec](spec/strict-args.md) and the [conformance corpus](conformance/) (vendored here from the monorepo).
