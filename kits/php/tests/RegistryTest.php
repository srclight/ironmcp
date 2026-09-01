<?php

declare(strict_types=1);

namespace IronMcp\Tests;

use IronMcp\Registry;
use IronMcp\RegistryEntry;
use PHPUnit\Framework\TestCase;

final class RegistryTest extends TestCase
{
    private string $dir;

    protected function setUp(): void
    {
        $this->dir = sys_get_temp_dir() . '/ironmcp_reg_' . bin2hex(random_bytes(6));
        mkdir($this->dir, 0o700, true);
    }

    protected function tearDown(): void
    {
        foreach (glob($this->dir . '/*') ?: [] as $f) {
            @unlink($f);
        }
        @rmdir($this->dir);
    }

    /** Invariant #9: sequential registers each lock the file — no entry is lost to a lost update. */
    public function testRegistersDoNotLoseAnEntry(): void
    {
        $reg = new Registry(dir: $this->dir, isPidAlive: static fn (int $_): bool => true);
        $reg->register(new RegistryEntry(id: 'a', namespace: 'test', pid: 1));
        $reg->register(new RegistryEntry(id: 'b', namespace: 'test', pid: 2));
        $reg->register(new RegistryEntry(id: 'c', namespace: 'test', pid: 3));
        $reg->register(new RegistryEntry(id: 'd', namespace: 'test', pid: 4));

        $ids = array_map(static fn (RegistryEntry $e): string => $e->id, $reg->discover());
        sort($ids);
        $this->assertSame(['a', 'b', 'c', 'd'], $ids);
    }

    /**
     * Invariant #9 (the lock, exercised concurrently): child processes racing to register must not
     * clobber each other — every one of them survives the read-modify-write.
     */
    public function testConcurrentRegistersFromChildProcessesLoseNothing(): void
    {
        if (!\function_exists('pcntl_fork')) {
            $this->markTestSkipped('pcntl not available — the single-process lock path is covered above');
        }
        $n = 8;
        $pids = [];
        for ($i = 0; $i < $n; ++$i) {
            $pid = pcntl_fork();
            if ($pid === 0) {
                // child: fresh Registry on the same dir, register one entry, exit.
                $reg = new Registry(dir: $this->dir, isPidAlive: static fn (int $_): bool => true);
                usleep(random_int(0, 3000));
                $reg->register(new RegistryEntry(id: "e{$i}", namespace: 'race', pid: 1000 + $i));
                exit(0);
            }
            $pids[] = $pid;
        }
        foreach ($pids as $pid) {
            pcntl_waitpid($pid, $status);
        }
        $reg = new Registry(dir: $this->dir, isPidAlive: static fn (int $_): bool => true);
        $this->assertCount($n, $reg->discover(), 'the O_EXCL lock must serialize every writer');
    }

    /** Invariant #10: discover prunes a dead pid and rewrites the file (lazy GC). */
    public function testDiscoverPrunesADeadPidAndRewrites(): void
    {
        $reg = new Registry(dir: $this->dir, isPidAlive: static fn (int $pid): bool => $pid !== 2);
        $reg->register(new RegistryEntry(id: 'a', namespace: 'test', pid: 1));
        $reg->register(new RegistryEntry(id: 'b', namespace: 'test', pid: 2)); // dead

        $this->assertSame(['a'], array_map(static fn (RegistryEntry $e): string => $e->id, $reg->discover()));
        // rewritten: a second discover still only sees the live one
        $this->assertSame(['a'], array_map(static fn (RegistryEntry $e): string => $e->id, $reg->discover()));

        $raw = json_decode((string) file_get_contents($this->dir . '/registry.json'), true);
        $this->assertArrayNotHasKey('b', $raw, 'the dead entry must be gone from the file');
    }

    public function testUnregisterRemovesAnEntry(): void
    {
        $reg = new Registry(dir: $this->dir, isPidAlive: static fn (int $_): bool => true);
        $reg->register(new RegistryEntry(id: 'a', namespace: 'test', pid: 1));
        $reg->unregister('a');
        $this->assertSame([], $reg->discover());
    }

    /** Invariant #3: the entry JSON is language-neutral and carries NO hand-kept tool list. */
    public function testEntryJsonIsLanguageNeutralAndCarriesNoToolList(): void
    {
        $j = (new RegistryEntry(
            id: 'x',
            namespace: 'ns',
            pid: 9,
            host: '127.0.0.1',
            port: 8080,
            transport: 'http',
            version: '1.0',
            codeSha: 'abc123',
            capabilities: ['tools' => []],
        ))->toArray();

        $this->assertSame('abc123', $j['code_sha']);       // snake_case, matching Dart
        $this->assertIsString($j['started_at']);
        $this->assertArrayNotHasKey('tools', $j);          // honesty: no drifting count
        $this->assertArrayNotHasKey('toolCount', $j);

        $e = RegistryEntry::fromArray($j);
        $this->assertSame('x', $e->id);
        $this->assertSame(8080, $e->port);
        $this->assertSame('http', $e->transport);
    }

    /**
     * The CANONICAL registry timestamp, pinned exactly: ISO-8601 UTC, millisecond precision (exactly
     * 3 fractional digits), trailing Z — e.g. 2026-09-01T10:35:34.123Z. Never a +00:00 offset, never
     * 6-digit microseconds. This is the format every kit must emit so registry.json is byte-identical
     * across languages; the compat audit found other kits drifting to +00:00 / 6-digit precision.
     */
    public function testStartedAtIsCanonicalMillisecondUtcZ(): void
    {
        $startedAt = (new RegistryEntry(id: 'x', namespace: 'ns', pid: 1))->toArray()['started_at'];
        $this->assertIsString($startedAt);
        // Exactly: YYYY-MM-DDTHH:MM:SS.mmmZ — 3 fractional digits, literal trailing Z.
        $this->assertMatchesRegularExpression(
            '/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/',
            $startedAt,
            'started_at must be ISO-8601 UTC with millisecond precision and a trailing Z',
        );
        $this->assertStringNotContainsString('+00:00', $startedAt, 'must use Z, never a +00:00 offset');
        // An explicitly supplied timestamp is preserved verbatim (round-trips unchanged).
        $explicit = '2026-09-01T10:35:34.123Z';
        $this->assertSame(
            $explicit,
            (new RegistryEntry(id: 'x', namespace: 'ns', pid: 1, startedAt: $explicit))->toArray()['started_at'],
        );
    }

    /**
     * The Dart-compat guarantee: the top-level file is a FLAT object keyed by entry id (not nested
     * by namespace), each value the exact snake_case entry shape — so a Dart server reading this
     * file gets valid IronMcpEntry maps. This is the estate-wide discovery fabric.
     */
    public function testOnDiskShapeIsFlatKeyedByIdMatchingDart(): void
    {
        $reg = new Registry(dir: $this->dir, isPidAlive: static fn (int $_): bool => true);
        $reg->register(new RegistryEntry(id: 'srv-1', namespace: 'iron', pid: 7, port: 8888, transport: 'http'));

        $txt = (string) file_get_contents($this->dir . '/registry.json');
        $decoded = json_decode($txt, true);

        $this->assertIsArray($decoded);
        $this->assertArrayHasKey('srv-1', $decoded, 'top-level map is keyed by entry id');
        $entry = $decoded['srv-1'];
        // Exactly the Dart field set (snake_case, optionals present because supplied).
        $this->assertSame('srv-1', $entry['id']);
        $this->assertSame('iron', $entry['namespace']);
        $this->assertSame(7, $entry['pid']);
        $this->assertSame(8888, $entry['port']);
        $this->assertSame('http', $entry['transport']);
        $this->assertArrayHasKey('capabilities', $entry);
        $this->assertArrayHasKey('started_at', $entry);
    }

    /**
     * Dart reads `capabilities` as a Map; a JSON [] would decode to a Dart List and throw. PHP
     * cannot distinguish [] from {} once decoded to an associative array, so an empty-capabilities
     * entry must survive REPEATED rewrites as {} on disk — never degrade to []. Guards the
     * object-decoding read path.
     */
    public function testEmptyCapabilitiesStayAnObjectAcrossRewrites(): void
    {
        $reg = new Registry(dir: $this->dir, isPidAlive: static fn (int $_): bool => true);
        $reg->register(new RegistryEntry(id: 'a', namespace: 'ns', pid: 1));            // empty caps
        $reg->register(new RegistryEntry(id: 'b', namespace: 'ns', pid: 2, capabilities: ['screenshot' => true]));
        $reg->register(new RegistryEntry(id: 'c', namespace: 'ns', pid: 3));            // forces a re-read/re-write of a and b

        $txt = (string) file_get_contents($this->dir . '/registry.json');
        // 'a' was written, then re-read and re-written twice; it must still be {} not [].
        $this->assertStringContainsString('"capabilities": {}', $txt);
        $this->assertStringNotContainsString('"capabilities": []', $txt);
        // The populated one is preserved verbatim.
        $this->assertStringContainsString('"screenshot": true', $txt);
    }
}
