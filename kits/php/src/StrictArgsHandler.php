<?php

declare(strict_types=1);

namespace IronMcp;

use Mcp\Capability\RegistryInterface;
use Mcp\Schema\Content\TextContent;
use Mcp\Schema\JsonRpc\Error;
use Mcp\Schema\JsonRpc\Request;
use Mcp\Schema\JsonRpc\Response;
use Mcp\Schema\Request\CallToolRequest;
use Mcp\Schema\Result\CallToolResult;
use Mcp\Server\Handler\Request\RequestHandlerInterface;
use Mcp\Server\Session\SessionInterface;

/**
 * The strict-args guard as a request handler. Added via Builder::addRequestHandler, it is tried
 * BEFORE the SDK's CallToolHandler (Builder merges user handlers first) and answers ONLY a
 * tools/call that carries an unknown argument — so a clean call, and an unknown tool, fall
 * through to the SDK. On an unknown argument it short-circuits with the ironmcp refusal shape
 * (an isError tool result + the bounded prose message + structuredContent.ironmcp), identical to
 * the Python and TypeScript kits, so the shared conformance corpus passes the same way.
 *
 * @implements RequestHandlerInterface<CallToolResult>
 */
final class StrictArgsHandler implements RequestHandlerInterface
{
    public function __construct(
        private readonly RegistryInterface $registry,
        private readonly string $reconnectHint = Messages::DEFAULT_RECONNECT_HINT,
    ) {
    }

    public function supports(Request $request): bool
    {
        if (!$request instanceof CallToolRequest) {
            return false;
        }
        $schema = $this->schemaFor($request->name);
        if ($schema === null) {
            return false; // unknown tool -> the SDK answers tool-not-found
        }

        return StrictArgs::check($schema, $request->arguments, $request->name)['ok'] === false;
    }

    public function handle(Request $request, SessionInterface $session): Response|Error
    {
        \assert($request instanceof CallToolRequest);
        $check = StrictArgs::check($this->schemaFor($request->name), $request->arguments, $request->name, $this->reconnectHint);
        \assert($check['ok'] === false); // supports() gated this

        $result = new CallToolResult(
            content: [new TextContent($check['message'])],
            isError: true,
            structuredContent: [
                'ironmcp' => [
                    'refused' => true,
                    'tool' => $request->name,
                    'unknown' => $check['unknown'],
                    'accepted' => $check['accepted'],
                ],
            ],
        );

        return new Response($request->getId(), $result);
    }

    /** @return array<string, mixed>|null */
    private function schemaFor(string $name): ?array
    {
        try {
            return $this->registry->getTool($name)->tool->inputSchema;
        } catch (\Throwable) {
            return null; // exception-safe: an unknown tool has no schema
        }
    }
}
