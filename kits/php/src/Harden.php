<?php

declare(strict_types=1);

namespace IronMcp;

use Mcp\Capability\Registry;
use Mcp\Capability\RegistryInterface;
use Mcp\Schema\Tool;
use Mcp\Server;
use Mcp\Server\Builder;

/**
 * The one-call entry: make an mcp/sdk server refuse unknown tool arguments and advertise exactly
 * what it enforces. It adds the StrictArgsHandler (the runtime refusal, in the ironmcp shape) and
 * stamps additionalProperties:false onto every registered tool schema (advertise == runtime; the
 * SDK's own Opis validation then also refuses, as defence in depth). The stamp runs AFTER build,
 * because tool schemas are reflection-generated during discovery/build.
 */
final class Harden
{
    /**
     * Wrap a Builder: inject the guard + stamp the built registry closed. Returns the built server.
     * Provides the registry itself so the guard and the stamp share one populated registry.
     */
    public static function server(Builder $builder, string $reconnectHint = Messages::DEFAULT_RECONNECT_HINT): Server
    {
        return self::serveHardened($builder, reconnectHint: $reconnectHint)->server;
    }

    /**
     * The one-call convenience serve entry. Hardens the builder exactly as {@see server()} does
     * (strict-args guard + every tool schema stamped closed) AND, when [allowedHosts] is given,
     * builds the DNS-rebinding {@see HostGuard} (invariant #4) and returns it alongside the server so
     * a caller of the CONVENIENCE path — not only the low-level HostGuard constructor — can enable
     * the guard. PHP serving is PHP-FPM/PSR-15-shaped, so the returned {@see HardenedApp::$hostGuard}
     * is enforced by the app's HTTP front controller before dispatch (see {@see HardenedApp}).
     *
     * @param iterable<string>|null $allowedHosts hosts the server legitimately answers as; when
     *                                            non-null a default-deny HostGuard is built and any
     *                                            other (rebinding) Host is refused. null opts out.
     */
    public static function serveHardened(
        Builder $builder,
        ?iterable $allowedHosts = null,
        string $reconnectHint = Messages::DEFAULT_RECONNECT_HINT,
    ): HardenedApp {
        $registry = new Registry();
        $builder->setRegistry($registry);
        $builder->addRequestHandler(new StrictArgsHandler($registry, $reconnectHint));
        $server = $builder->build();
        self::registry($registry);

        $hostGuard = $allowedHosts !== null ? new HostGuard($allowedHosts) : null;

        return new HardenedApp($server, $hostGuard);
    }

    /** Stamp additionalProperties:false onto every registered tool schema (post-build primitive). */
    public static function registry(RegistryInterface $registry): void
    {
        // getTools() advertises Tool objects (the tools/list payload); getTool($name) returns the
        // ToolReference that also carries the handler needed to re-register.
        foreach ($registry->getTools()->references as $tool) {
            $closed = StrictArgs::stampClosed($tool->inputSchema);
            if ($closed === $tool->inputSchema) {
                continue; // opted open or unintrospectable — leave it
            }
            $handler = $registry->getTool($tool->name)->handler;
            $stamped = new Tool(
                $tool->name,
                $tool->title,
                $closed,
                $tool->description,
                $tool->annotations,
                $tool->icons,
                $tool->meta,
                $tool->outputSchema,
            );
            $registry->unregisterTool($tool->name);
            $registry->registerTool($stamped, $handler);
        }
    }
}
