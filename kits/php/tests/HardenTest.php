<?php

declare(strict_types=1);

namespace IronMcp\Tests;

use IronMcp\Harden;
use IronMcp\HostGuard;
use IronMcp\StrictArgsHandler;
use Mcp\Capability\Registry;
use Mcp\Schema\Request\CallToolRequest;
use Mcp\Schema\Result\CallToolResult;
use Mcp\Schema\Tool;
use Mcp\Server;
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

    /**
     * Gap #6: the skip branch (`$closed === $tool->inputSchema` -> continue). An opted-open tool
     * (additionalProperties:true) and an unintrospectable tool (no `properties`) must be left in the
     * registry UNCHANGED — never unregistered/re-registered — while a normal tool alongside them is
     * still stamped closed. An over-eager stamp of the opted-open tool would silently close it.
     */
    public function testHardenLeavesOptedOpenAndUnintrospectableToolsRegisteredUnchanged(): void
    {
        $r = new Registry();
        $openSchema = ['type' => 'object', 'properties' => ['a' => []], 'additionalProperties' => true];
        $bareSchema = ['type' => 'object']; // no properties -> unintrospectable
        $closableSchema = ['type' => 'object', 'properties' => ['a' => ['type' => 'string']]];
        $r->registerTool(new Tool('opened', null, $openSchema, null, null), static fn (): string => 'x');
        $r->registerTool(new Tool('bare', null, $bareSchema, null, null), static fn (): string => 'y');
        $r->registerTool(new Tool('closable', null, $closableSchema, null, null), static fn (): string => 'z');

        // Capture the exact Tool object identities before hardening.
        $openedBefore = $r->getTool('opened')->tool;
        $bareBefore = $r->getTool('bare')->tool;

        Harden::registry($r);

        // The opted-open tool keeps additionalProperties:true and is the SAME Tool instance (untouched).
        $openedAfter = $r->getTool('opened')->tool;
        $this->assertTrue($openedAfter->inputSchema['additionalProperties'], 'opted-open must stay open');
        $this->assertSame($openedBefore, $openedAfter, 'opted-open tool must not be re-registered');

        // The unintrospectable tool is untouched (no additionalProperties key appears) and same instance.
        $bareAfter = $r->getTool('bare')->tool;
        $this->assertArrayNotHasKey('additionalProperties', $bareAfter->inputSchema);
        $this->assertSame($bareBefore, $bareAfter, 'unintrospectable tool must not be re-registered');

        // The normal tool alongside them IS stamped closed.
        $this->assertFalse($r->getTool('closable')->tool->inputSchema['additionalProperties']);
    }

    private function builderWithSearch(): Server\Builder
    {
        return Server::builder()
            ->setServerInfo('search', '1.0.0')
            ->addTool(
                static fn (string $query): string => $query,
                name: 'search',
                inputSchema: ['type' => 'object', 'properties' => ['query' => ['type' => 'string']], 'required' => ['query']],
            );
    }

    /**
     * Cross-cutting fix #1: the one-call convenience serve entry must FORWARD an allowedHosts list
     * into the DNS-rebinding HostGuard (invariant #4), so a user of the convenience path — not only
     * the low-level HostGuard constructor — can enable the guard. A convenience-served app must then
     * refuse a rebinding Host while still answering the hosts it legitimately serves.
     */
    public function testConvenienceServeForwardsAllowedHostsIntoTheGuard(): void
    {
        $app = Harden::serveHardened($this->builderWithSearch(), allowedHosts: ['wasabi.local', 'localhost']);

        $this->assertInstanceOf(Server::class, $app->server, 'the hardened server is still built');
        $this->assertInstanceOf(HostGuard::class, $app->hostGuard, 'allowedHosts must build a HostGuard');

        // The convenience-served app refuses a rebinding attacker's Host...
        $this->assertFalse($app->hostGuard->accepts('evil.example.com'));
        $this->assertFalse($app->hostGuard->accepts('evil.example.com:8888'));
        // ...while still accepting the hosts it was told it legitimately serves (with or without port).
        $this->assertTrue($app->hostGuard->accepts('wasabi.local'));
        $this->assertTrue($app->hostGuard->accepts('localhost:18888'));
    }

    /** Without allowedHosts the convenience opts the guard out (hostGuard is null), server still built. */
    public function testConvenienceServeWithoutAllowedHostsHasNoGuard(): void
    {
        $app = Harden::serveHardened($this->builderWithSearch());
        $this->assertInstanceOf(Server::class, $app->server);
        $this->assertNull($app->hostGuard, 'no allowedHosts -> guard opted out');
    }

    public function testTheRefusalNeverEchoesAValue(): void
    {
        $h = new StrictArgsHandler($this->registryWithEcho());
        $req = $this->req('echo', ['a' => 'x', 'secret' => 'SENTINEL_9f3a']);
        $resp = $h->handle($req, $this->createMock(SessionInterface::class));
        $this->assertStringNotContainsString('SENTINEL_9f3a', json_encode($resp->result, JSON_THROW_ON_ERROR));
    }
}
