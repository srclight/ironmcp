<?php

declare(strict_types=1);

namespace IronMcp;

use Mcp\Server;

/**
 * What the one-call convenience {@see Harden::serveHardened()} hands back: the built, hardened
 * {@see Server} together with the {@see HostGuard} the convenience built from `allowedHosts`.
 *
 * PHP serving is PHP-FPM/PSR-15-shaped — the kit does not own the socket — so the DNS-rebinding
 * guard (invariant #4) is ENFORCED by the app's HTTP front controller, exactly as the kit's other
 * guards are (see AuthTest's `gate()`): read the `Host` header, and reject before dispatch when the
 * guard refuses it. This bundle carries that guard so the convenience path — not only the low-level
 * {@see HostGuard} constructor — can enable it:
 *
 * ```php
 * $app = Harden::serveHardened($builder, allowedHosts: ['wasabi.local', 'localhost']);
 * if (!$app->hostGuard?->accepts($_SERVER['HTTP_HOST'] ?? null)) {
 *     http_response_code(403); exit; // rebinding Host refused
 * }
 * $app->server->run($transport);
 * ```
 *
 * `hostGuard` is null when the convenience was called without `allowedHosts` (guard opted out).
 */
final class HardenedApp
{
    public function __construct(
        public readonly Server $server,
        public readonly ?HostGuard $hostGuard = null,
    ) {
    }
}
