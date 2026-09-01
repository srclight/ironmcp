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

    /**
     * Canonical fix #3 (persistence, not just an in-memory re-prune): after discover() prunes a dead
     * pid it MUST rewrite registry.json, so a FRESH Registry instance — one that has never seen the
     * dead entry and treats every pid as alive — reading the file from disk sees only the live entry.
     * This proves invariant #10's lazy GC is durable, not a per-process illusion.
     */
    public function testDeadPidPruneIsPersistedAndSeenByAFreshReader(): void
    {
        $pruner = new Registry(dir: $this->dir, isPidAlive: static fn (int $pid): bool => $pid !== 2);
        $pruner->register(new RegistryEntry(id: 'a', namespace: 'test', pid: 1));
        $pruner->register(new RegistryEntry(id: 'b', namespace: 'test', pid: 2)); // dead
        $pruner->discover(); // prunes 'b' and MUST rewrite the file

        // A brand-new instance, all-pids-alive, reading only what is on disk.
        $fresh = new Registry(dir: $this->dir, isPidAlive: static fn (int $_): bool => true);
        $ids = array_map(static fn (RegistryEntry $e): string => $e->id, $fresh->discover());
        $this->assertSame(['a'], $ids, 'the dead entry must be gone from disk, not merely re-pruned in memory');
    }

    /**
     * Gap #5 / canonical fix #5: a corrupt, empty, or non-object registry.json must make
     * discover()/register() START FRESH rather than crash. Exercises all three read() recovery
     * branches: a JsonException on garbage, an empty/whitespace-only file, and a top-level JSON array.
     */
    public function testCorruptEmptyOrNonObjectRegistryStartsFresh(): void
    {
        foreach (['{ this is not json', '', "   \n  ", '["a", "b"]'] as $bad) {
            file_put_contents($this->dir . '/registry.json', $bad);

            $reg = new Registry(dir: $this->dir, isPidAlive: static fn (int $_): bool => true);
            $this->assertSame([], $reg->discover(), "discover() must start fresh on malformed content: {$bad}");

            // register() must succeed on top of the malformed file, replacing it with a valid object.
            $reg->register(new RegistryEntry(id: 'x', namespace: 'ns', pid: 1));
            $this->assertSame(['x'], array_map(static fn (RegistryEntry $e): string => $e->id, $reg->discover()));
        }
    }

    /**
     * discover()'s malformed-ENTRY prune: a stray scalar or [] stored under a key (not a valid entry
     * object) is dropped and the file rewritten. Proven durable via a fresh reader.
     */
    public function testDiscoverPrunesAMalformedEntryAndPersists(): void
    {
        // Hand-craft a file: one valid entry plus two malformed values under keys.
        $valid = (new RegistryEntry(id: 'good', namespace: 'ns', pid: 1))->toArray();
        $raw = ['good' => $valid, 'scalar' => 42, 'list' => ['x', 'y']];
        file_put_contents($this->dir . '/registry.json', json_encode($raw, JSON_THROW_ON_ERROR));

        $reg = new Registry(dir: $this->dir, isPidAlive: static fn (int $_): bool => true);
        $ids = array_map(static fn (RegistryEntry $e): string => $e->id, $reg->discover());
        $this->assertSame(['good'], $ids, 'malformed non-object entries must be pruned');

        // Persisted: a fresh reader sees only the good entry, and the malformed keys are gone from disk.
        $onDisk = json_decode((string) file_get_contents($this->dir . '/registry.json'), true);
        $this->assertArrayHasKey('good', $onDisk);
        $this->assertArrayNotHasKey('scalar', $onDisk);
        $this->assertArrayNotHasKey('list', $onDisk);
    }

    /**
     * withLock stale-lock steal: a crashed holder can leave a lock file behind. Past staleLockAfter
     * the lock is stolen so a live writer is not blocked forever. With staleLockAfter=0 any existing
     * lock is immediately stale, so register() steals it and still lands the entry.
     */
    public function testWithLockStealsAStaleLock(): void
    {
        // Simulate a crashed holder's leftover lock.
        file_put_contents($this->dir . '/registry.json.lock', '');

        $reg = new Registry(
            dir: $this->dir,
            isPidAlive: static fn (int $_): bool => true,
            lockTimeout: 1.0,
            staleLockAfter: 0.0, // any existing lock is instantly stale
        );
        $reg->register(new RegistryEntry(id: 'a', namespace: 'ns', pid: 1));

        $this->assertSame(['a'], array_map(static fn (RegistryEntry $e): string => $e->id, $reg->discover()));
    }

    /**
     * withLock give-up-and-proceed: when a FRESH (non-stale) lock is held and lockTimeout elapses,
     * the writer proceeds best-effort WITHOUT the lock rather than losing the write — and, because it
     * never acquired the lock, it must not delete the holder's lock on the way out.
     */
    public function testWithLockProceedsBestEffortWhenLockHeldPastTimeout(): void
    {
        $lock = $this->dir . '/registry.json.lock';
        file_put_contents($lock, ''); // a fresh lock, held by (a simulated) live holder

        $reg = new Registry(
            dir: $this->dir,
            isPidAlive: static fn (int $_): bool => true,
            lockTimeout: 0.0,     // deadline is now: give up immediately
            staleLockAfter: 1000, // never steal — the lock looks freshly held
        );
        $reg->register(new RegistryEntry(id: 'a', namespace: 'ns', pid: 1));

        // The write still landed despite not holding the lock (best-effort proceed)...
        $this->assertSame(['a'], array_map(static fn (RegistryEntry $e): string => $e->id, $reg->discover()));
        // ...and the holder's lock was left in place (we never owned it, so we must not unlink it).
        $this->assertFileExists($lock, 'a proceed-without-lock writer must not remove a lock it never held');
    }

    /**
     * The DEFAULT liveness probe (no injected stub): the current process's own pid is alive, so an
     * entry keyed to it survives discover(); a reaped child's pid is dead, so its entry is pruned.
     * Every other Registry test injects isPidAlive — this is the only exercise of the real POSIX/proc
     * kill(0) path.
     */
    public function testDefaultPidProbeKeepsSelfAndPrunesADeadChild(): void
    {
        $reg = new Registry(dir: $this->dir); // REAL pidAliveDefault, no stub
        $reg->register(new RegistryEntry(id: 'self', namespace: 'ns', pid: getmypid() ?: 1));

        if (\function_exists('pcntl_fork')) {
            $child = pcntl_fork();
            if ($child === 0) {
                exit(0); // child dies immediately
            }
            pcntl_waitpid($child, $status); // reap -> $child pid is now dead
            $reg->register(new RegistryEntry(id: 'dead', namespace: 'ns', pid: $child));

            $ids = array_map(static fn (RegistryEntry $e): string => $e->id, $reg->discover());
            $this->assertContains('self', $ids, 'the running process pid must read as alive');
            $this->assertNotContains('dead', $ids, 'a reaped child pid must read as dead and be pruned');
        } else {
            $this->assertContains(
                'self',
                array_map(static fn (RegistryEntry $e): string => $e->id, $reg->discover()),
                'the running process pid must read as alive',
            );
        }
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
     * Gap: Registry::defaultDir() — the XDG precedence that is the linchpin of cross-kit discovery
     * ("a Dart server and a PHP server share ONE file"). Every other test injects an explicit dir:,
     * so this resolution was never exercised. Precedence: XDG_RUNTIME_DIR, then XDG_STATE_HOME, then
     * $HOME/.local/state, then './.local/state' — always with '/ironmcp' appended.
     */
    public function testDefaultDirXdgPrecedence(): void
    {
        $keys = ['XDG_RUNTIME_DIR', 'XDG_STATE_HOME', 'HOME'];
        $saved = [];
        foreach ($keys as $k) {
            $saved[$k] = getenv($k); // false when unset
        }

        try {
            // 1. XDG_RUNTIME_DIR wins over everything else.
            putenv('XDG_RUNTIME_DIR=/run/user/1000');
            putenv('XDG_STATE_HOME=/state');
            putenv('HOME=/home/tim');
            $this->assertSame('/run/user/1000/ironmcp', Registry::defaultDir());

            // 2. No runtime dir -> XDG_STATE_HOME.
            putenv('XDG_RUNTIME_DIR');
            $this->assertSame('/state/ironmcp', Registry::defaultDir());

            // 3. Neither XDG var -> $HOME/.local/state.
            putenv('XDG_STATE_HOME');
            $this->assertSame('/home/tim/.local/state/ironmcp', Registry::defaultDir());

            // 4. No HOME either -> the '.' fallback.
            putenv('HOME');
            $this->assertSame('./.local/state/ironmcp', Registry::defaultDir());
        } finally {
            foreach ($saved as $k => $v) {
                $v === false ? putenv($k) : putenv("{$k}={$v}");
            }
        }
    }

    /**
     * Gap: the ONE place PHP could silently diverge from a peer. PHP/Dart use `??`, so an EMPTY
     * XDG_RUNTIME_DIR ('' — set but blank) is USED, yielding base '' and dir '/ironmcp'. The TS
     * (`||`) and Python (`or`) peers instead skip an empty XDG var. This pins PHP's documented
     * `??`-semantics so the cross-kit inconsistency can never drift unnoticed.
     */
    public function testDefaultDirUsesAnEmptyXdgVarPerPhpNullCoalescing(): void
    {
        $keys = ['XDG_RUNTIME_DIR', 'XDG_STATE_HOME', 'HOME'];
        $saved = [];
        foreach ($keys as $k) {
            $saved[$k] = getenv($k);
        }

        try {
            putenv('XDG_RUNTIME_DIR='); // set-but-empty: `??` keeps '' (unlike `||`/`or`)
            putenv('XDG_STATE_HOME=/state');
            putenv('HOME=/home/tim');
            $this->assertSame('/ironmcp', Registry::defaultDir(), 'an empty XDG var is USED under `??`, giving base ""');
        } finally {
            foreach ($saved as $k => $v) {
                $v === false ? putenv($k) : putenv("{$k}={$v}");
            }
        }
    }

    /**
     * Gap: discover()'s disk -> RegistryEntry::fromArray round-trip of a POPULATED capabilities map
     * must return the map INTACT — this is the actual cross-kit interop READ path (a Dart/Node writer
     * stores {screenshot:true}, a PHP consumer reads it back as an associative array via the
     * stdClass -> (array) cast). The empty-{} and on-disk-text cases are covered elsewhere; this pins
     * the populated read itself, not merely how it was written.
     */
    public function testDiscoverReturnsAPopulatedCapabilitiesMapIntact(): void
    {
        $reg = new Registry(dir: $this->dir, isPidAlive: static fn (int $_): bool => true);
        $reg->register(new RegistryEntry(
            id: 'srv',
            namespace: 'ns',
            pid: 1,
            capabilities: ['screenshot' => true, 'annotate' => false, 'max' => 16],
        ));

        $found = $reg->discover();
        $this->assertCount(1, $found);
        $this->assertSame(
            ['screenshot' => true, 'annotate' => false, 'max' => 16],
            $found[0]->capabilities,
            'a populated capabilities map must round-trip through discover() as an intact assoc array',
        );
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
