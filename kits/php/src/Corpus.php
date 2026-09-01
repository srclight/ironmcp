<?php

declare(strict_types=1);

namespace IronMcp;

use Mcp\Capability\Discovery\SchemaValidator;
use Mcp\Capability\Registry;
use Mcp\Schema\Request\CallToolRequest;
use Mcp\Schema\Tool;
use Mcp\Server\Session\InMemorySessionStore;
use Mcp\Server\Session\Session;
use Psr\Log\NullLogger;

/**
 * The conformance corpus, driven at the Protocol's dispatch point. A "driver" answers a
 * (tool, arguments) with the verdict the server would give — the hardened driver runs the real
 * StrictArgsHandler; the bare driver runs the SDK's own Opis validator against the open schemas.
 * A conforming (hardened) server passes every case; a bare one FAILS (a corpus never watched to
 * fail is theatre).
 */
final class Corpus
{
    /** @var array<string, mixed> */
    private const ECHO_SCHEMA = ['type' => 'object', 'properties' => ['a' => ['type' => 'string'], 'b' => ['type' => 'string']]];

    /** @return list<array<string, mixed>> */
    public static function load(string $casesDir): array
    {
        $cases = [];
        foreach (glob(rtrim($casesDir, '/') . '/*.json') ?: [] as $file) {
            $cases[] = json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
        }

        return $cases;
    }

    /**
     * @param callable(string, array<string, mixed>): array{isError: bool, text: string, structured: ?array} $driver
     */
    public static function assertEnforces(callable $driver, string $casesDir): int
    {
        $cases = self::load($casesDir);
        $failures = [];
        foreach ($cases as $c) {
            $r = $driver($c['tool'], $c['arguments']);
            if (($c['expect'] === 'refuse') !== $r['isError']) {
                $failures[] = "{$c['id']}: expected {$c['expect']}, isError=" . var_export($r['isError'], true);
            }
            foreach ($c['expect_message_contains'] ?? [] as $s) {
                if (!str_contains($r['text'], $s)) {
                    $failures[] = "{$c['id']}: message missing '{$s}'";
                }
            }
            foreach ($c['expect_message_excludes'] ?? [] as $s) {
                if (str_contains($r['text'], $s)) {
                    $failures[] = "{$c['id']}: message leaked '{$s}'";
                }
            }
            foreach ($c['expect_structured'] ?? [] as $field => $expected) {
                $iron = $r['structured']['ironmcp'] ?? null;
                $got = is_array($iron) ? ($iron[$field] ?? null) : null;
                if (!is_array($got) || array_diff($expected, $got) !== []) {
                    $failures[] = "{$c['id']}: structuredContent.ironmcp.{$field} missing " . json_encode($expected);
                }
            }
        }
        if ($failures !== []) {
            throw new \RuntimeException("conformance failures:\n  " . implode("\n  ", $failures));
        }

        return count($cases);
    }

    /** The hardened driver: the real StrictArgsHandler over a closed-schema fixture registry. */
    public static function hardenedDriver(): callable
    {
        $registry = self::fixtureRegistry();
        Harden::registry($registry);
        $handler = new StrictArgsHandler($registry);
        $session = new Session(new InMemorySessionStore());

        return static function (string $tool, array $args) use ($handler, $session): array {
            $req = CallToolRequest::fromArray([
                'jsonrpc' => '2.0', 'id' => 1, 'method' => 'tools/call',
                'params' => ['name' => $tool, 'arguments' => $args],
            ]);
            if (!$handler->supports($req)) {
                return ['isError' => false, 'text' => '', 'structured' => null];
            }
            $result = $handler->handle($req, $session)->result;
            $text = implode(' ', array_map(static fn ($c): string => $c->text ?? '', $result->content));

            return ['isError' => $result->isError, 'text' => $text, 'structured' => $result->structuredContent];
        };
    }

    /** The bare driver: the SDK's own Opis validator over the OPEN fixture schemas (the drop). */
    public static function bareDriver(): callable
    {
        $validator = new SchemaValidator(new NullLogger());
        $schemas = ['echo' => self::ECHO_SCHEMA, 'ping' => ['type' => 'object', 'properties' => new \stdClass()]];

        return static function (string $tool, array $args) use ($validator, $schemas): array {
            $schema = $schemas[$tool] ?? ['type' => 'object'];
            $errors = $validator->validateAgainstJsonSchema($args, $schema);

            return ['isError' => $errors !== [], 'text' => '', 'structured' => null];
        };
    }

    private static function fixtureRegistry(): Registry
    {
        $registry = new Registry();
        $registry->registerTool(
            new Tool('echo', null, self::ECHO_SCHEMA, null, null),
            static fn (string $a, string $b = 'default'): string => "{$a}|{$b}",
        );
        $registry->registerTool(
            new Tool('ping', null, ['type' => 'object', 'properties' => new \stdClass()], null, null),
            static fn (): string => 'pong',
        );

        return $registry;
    }
}
