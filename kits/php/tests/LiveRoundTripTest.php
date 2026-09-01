<?php

declare(strict_types=1);

namespace IronMcp\Tests;

use IronMcp\Harden;
use Mcp\Server;
use Mcp\Server\Transport\StdioTransport;
use PHPUnit\Framework\TestCase;

/**
 * Live client<->server round-trip conformance over the REAL transport.
 *
 * The pure StrictArgs/StrictArgsHandler tests exercise the guard logic and the handler-dispatch
 * point in isolation. They cannot catch a transport-level bug — the class of miss that got past the
 * Dart pure unit tests: advertisement (tools/list) and runtime (tools/call) agreeing at the guard
 * but disagreeing once the SDK's MessageFactory, session resolution, handler ordering and JSON-RPC
 * serialization sit between the client and the tool.
 *
 * So this drives a genuine MCP session end-to-end: a client speaks JSON-RPC (initialize ->
 * notifications/initialized -> tools/list / tools/call) to a HARDENED server across the SDK's real
 * StdioTransport, wired to in-process pipes. Nothing here reaches into the guard directly — every
 * assertion is made on the bytes the server wrote back to the client.
 *
 * StdioTransport is the SDK transport that carries the full handshake era over a plain byte stream,
 * which makes it the closest thing to a real client<->server pairing the mcp/sdk exposes without
 * spawning a second process. (InMemoryTransport only replays canned input and discards the server's
 * replies — it cannot observe a round-trip response, per the kit notes.)
 */
final class LiveRoundTripTest extends TestCase
{
    /** The echo tool's declared object schema: `a` required, `b` optional. */
    private const ECHO_SCHEMA = [
        'type' => 'object',
        'properties' => ['a' => ['type' => 'string'], 'b' => ['type' => 'string']],
        'required' => ['a'],
    ];

    /**
     * Build a hardened server exposing a single `echo` tool, feed it the given JSON-RPC messages
     * over a REAL StdioTransport (backed by on-disk pipes so the stream survives the transport's
     * close()), and return every response the server emitted, keyed by JSON-RPC id.
     *
     * @param list<array<string, mixed>> $messages client->server JSON-RPC frames, in order
     *
     * @return array<int|string, array<string, mixed>> responses keyed by id
     */
    private function roundTrip(array $messages): array
    {
        $builder = Server::builder()
            ->setServerInfo('ironmcp-roundtrip', '1.0.0')
            ->addTool(
                handler: static fn (string $a, string $b = 'default'): string => "{$a}|{$b}",
                name: 'echo',
                description: 'echo tool',
                inputSchema: self::ECHO_SCHEMA,
            );
        // Harden::server injects the StrictArgsHandler AND stamps every schema additionalProperties:false.
        $server = Harden::server($builder);

        $ndjson = '';
        foreach ($messages as $m) {
            $ndjson .= json_encode($m, \JSON_THROW_ON_ERROR) . "\n";
        }

        $inFile = tempnam(sys_get_temp_dir(), 'ironmcp_in_');
        $outFile = tempnam(sys_get_temp_dir(), 'ironmcp_out_');
        self::assertIsString($inFile);
        self::assertIsString($outFile);
        file_put_contents($inFile, $ndjson);

        try {
            $in = fopen($inFile, 'r');
            $out = fopen($outFile, 'w');
            self::assertIsResource($in);
            self::assertIsResource($out);
            // run() drives the real server loop: parse NDJSON, resolve session, dispatch, serialize.
            $server->run(new StdioTransport($in, $out));

            $responses = [];
            foreach (explode("\n", trim((string) file_get_contents($outFile))) as $line) {
                if ($line === '') {
                    continue;
                }
                $decoded = json_decode($line, true, 512, \JSON_THROW_ON_ERROR);
                if (\is_array($decoded) && isset($decoded['id'])) {
                    $responses[$decoded['id']] = $decoded;
                }
            }

            return $responses;
        } finally {
            @unlink($inFile);
            @unlink($outFile);
        }
    }

    /** The three-frame prelude every session needs before it may call a tool. */
    private function handshake(): array
    {
        return [
            [
                'jsonrpc' => '2.0',
                'id' => 1,
                'method' => 'initialize',
                'params' => [
                    'protocolVersion' => '2025-06-18',
                    'capabilities' => new \stdClass(),
                    'clientInfo' => ['name' => 'test-client', 'version' => '1.0.0'],
                ],
            ],
            ['jsonrpc' => '2.0', 'method' => 'notifications/initialized'],
        ];
    }

    /** The handshake alone must complete — a sanity check that the live pairing works at all. */
    public function testInitializeHandshakeCompletesOverTheWire(): void
    {
        $responses = $this->roundTrip($this->handshake());
        $this->assertArrayHasKey(1, $responses, 'the server must answer initialize');
        $this->assertSame('2025-06-18', $responses[1]['result']['protocolVersion']);
        $this->assertArrayHasKey('tools', $responses[1]['result']['capabilities']);
    }

    /** A clean tools/call runs end-to-end and returns the tool's real output. */
    public function testCleanCallRunsAndReturnsResultOverTheWire(): void
    {
        $messages = array_merge($this->handshake(), [[
            'jsonrpc' => '2.0',
            'id' => 2,
            'method' => 'tools/call',
            'params' => ['name' => 'echo', 'arguments' => ['a' => 'hello', 'b' => 'world']],
        ]]);

        $responses = $this->roundTrip($messages);
        $this->assertArrayHasKey(2, $responses);
        $result = $responses[2]['result'];
        $this->assertFalse($result['isError'], 'a declared-argument call must not be an error');
        $this->assertSame('hello|world', $result['content'][0]['text'], 'the tool actually executed');
    }

    /**
     * The core conformance claim, proven end-to-end: a tools/call carrying ONE undeclared argument
     * is REFUSED across the real transport, in the ironmcp shape, and the tool never runs.
     */
    public function testUndeclaredArgIsRefusedOverTheWire(): void
    {
        $messages = array_merge($this->handshake(), [[
            'jsonrpc' => '2.0',
            'id' => 3,
            'method' => 'tools/call',
            'params' => ['name' => 'echo', 'arguments' => ['a' => 'hello', 'typo' => 'ignored']],
        ]]);

        $responses = $this->roundTrip($messages);
        $this->assertArrayHasKey(3, $responses);
        $result = $responses[3]['result'];

        $this->assertTrue($result['isError'], 'an undeclared argument must be refused');
        $this->assertStringContainsString('unknown argument(s): typo', $result['content'][0]['text']);
        $this->assertStringContainsString('Nothing was executed', $result['content'][0]['text']);

        $ironmcp = $result['structuredContent']['ironmcp'];
        $this->assertTrue($ironmcp['refused']);
        $this->assertSame('echo', $ironmcp['tool']);
        $this->assertSame(['typo'], $ironmcp['unknown']);
        $this->assertContains('a', $ironmcp['accepted']);
        $this->assertContains('b', $ironmcp['accepted']);
    }

    /**
     * Advertisement == runtime, proven over the wire in a SINGLE session: the schema the server
     * ADVERTISES via tools/list carries additionalProperties:false, and a call that violates it is
     * REFUSED at runtime. This is exactly the invariant the transport-level Dart bug slipped past —
     * the two facts agreeing only when observed together, through the real MessageFactory and
     * serializer, not read off the in-process registry.
     */
    public function testAdvertisedSchemaIsClosedAndRuntimeRefusesToMatchOverTheWire(): void
    {
        $messages = array_merge($this->handshake(), [
            ['jsonrpc' => '2.0', 'id' => 4, 'method' => 'tools/list', 'params' => new \stdClass()],
            [
                'jsonrpc' => '2.0',
                'id' => 5,
                'method' => 'tools/call',
                'params' => ['name' => 'echo', 'arguments' => ['a' => 'ok', 'extra' => 1]],
            ],
        ]);

        $responses = $this->roundTrip($messages);

        // Advertisement: the closed schema is what the client sees in tools/list.
        $tools = $responses[4]['result']['tools'];
        $echo = null;
        foreach ($tools as $t) {
            if ($t['name'] === 'echo') {
                $echo = $t;
                break;
            }
        }
        $this->assertNotNull($echo, 'echo must appear in tools/list');
        $this->assertFalse(
            $echo['inputSchema']['additionalProperties'],
            'the advertised schema must declare additionalProperties:false',
        );

        // Runtime: a call that violates that advertised closure is refused.
        $this->assertTrue($responses[5]['result']['isError'], 'runtime must refuse what the schema forbids');
        $this->assertSame(['extra'], $responses[5]['result']['structuredContent']['ironmcp']['unknown']);
    }

    /**
     * The refusal must never echo a rejected argument's VALUE back over the wire — a hostile or
     * secret-bearing value in an undeclared key must not survive into the response bytes.
     */
    public function testRefusalNeverEchoesTheValueOverTheWire(): void
    {
        $messages = array_merge($this->handshake(), [[
            'jsonrpc' => '2.0',
            'id' => 6,
            'method' => 'tools/call',
            'params' => ['name' => 'echo', 'arguments' => ['a' => 'ok', 'secret' => 'SENTINEL_9f3a']],
        ]]);

        $responses = $this->roundTrip($messages);
        $this->assertTrue($responses[6]['result']['isError']);
        $this->assertStringNotContainsString(
            'SENTINEL_9f3a',
            json_encode($responses[6], \JSON_THROW_ON_ERROR),
            'the rejected value must never appear in the response',
        );
        // The KEY is named (so the caller can fix the call); only the value is withheld.
        $this->assertSame(['secret'], $responses[6]['result']['structuredContent']['ironmcp']['unknown']);
    }
}
