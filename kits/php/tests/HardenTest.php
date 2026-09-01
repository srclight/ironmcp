<?php

declare(strict_types=1);

namespace IronMcp\Tests;

use IronMcp\Harden;
use IronMcp\StrictArgsHandler;
use Mcp\Capability\Registry;
use Mcp\Schema\Request\CallToolRequest;
use Mcp\Schema\Result\CallToolResult;
use Mcp\Schema\Tool;
use Mcp\Server\Session\SessionInterface;
use PHPUnit\Framework\TestCase;

final class HardenTest extends TestCase
{
    /** Build a CallToolRequest the way the protocol does — with a JSON-RPC id. */
    private function req(string $name, array $args): CallToolRequest
    {
        return CallToolRequest::fromArray([
            'jsonrpc' => '2.0',
            'id' => 2,
            'method' => 'tools/call',
            'params' => ['name' => $name, 'arguments' => $args],
        ]);
    }

    private function registryWithEcho(): Registry
    {
        $r = new Registry();
        $schema = ['type' => 'object', 'properties' => ['a' => ['type' => 'string'], 'b' => ['type' => 'string']], 'required' => ['a']];
        $r->registerTool(new Tool('echo', null, $schema, null, null), static fn (string $a, string $b = 'default'): string => "{$a}|{$b}");

        return $r;
    }

    public function testGuardRefusesUnknownArgWithIronmcpShape(): void
    {
        $h = new StrictArgsHandler($this->registryWithEcho());
        $req = $this->req('echo', ['a' => 'x', 'typo' => 'ignored']);
        $this->assertTrue($h->supports($req));

        $resp = $h->handle($req, $this->createMock(SessionInterface::class));
        $result = $resp->result;
        $this->assertInstanceOf(CallToolResult::class, $result);
        $this->assertTrue($result->isError);
        $text = $result->content[0]->text;
        $this->assertStringContainsString('unknown argument(s): typo', $text);
        $this->assertStringContainsString('Nothing was executed', $text);
        $this->assertSame(['typo'], $result->structuredContent['ironmcp']['unknown']);
        $this->assertContains('a', $result->structuredContent['ironmcp']['accepted']);
    }

    public function testGuardDeclinesACleanCall(): void
    {
        $h = new StrictArgsHandler($this->registryWithEcho());
        $this->assertFalse($h->supports($this->req('echo', ['a' => 'x'])));
    }

    public function testGuardDeclinesAnUnknownTool(): void
    {
        $h = new StrictArgsHandler($this->registryWithEcho());
        $this->assertFalse($h->supports($this->req('nonexistent', ['x' => 1])));
    }

    public function testHardenStampsSchemasClosed(): void
    {
        $r = $this->registryWithEcho();
        $this->assertArrayNotHasKey('additionalProperties', $r->getTool('echo')->tool->inputSchema);
        Harden::registry($r);
        $this->assertFalse($r->getTool('echo')->tool->inputSchema['additionalProperties']);
    }

    public function testTheRefusalNeverEchoesAValue(): void
    {
        $h = new StrictArgsHandler($this->registryWithEcho());
        $req = $this->req('echo', ['a' => 'x', 'secret' => 'SENTINEL_9f3a']);
        $resp = $h->handle($req, $this->createMock(SessionInterface::class));
        $this->assertStringNotContainsString('SENTINEL_9f3a', json_encode($resp->result, JSON_THROW_ON_ERROR));
    }
}
