<?php

declare(strict_types=1);

namespace IronMcp;

/**
 * Self-discovery of ironmcp servers. File-backed, with a cross-process O_EXCL lock around every
 * read-modify-write (closes the lost-update TOCTOU, invariant #9), pid-liveness pruning on read
 * (lazy GC, invariant #10), and an XDG path (not ~/.loqu8). The `namespace` field on each entry
 * keeps it estate-wide rather than Loqu8-only.
 *
 * On-disk format is byte-compatible with the Dart `IronMcpRegistry`
 * (kits/dart/lib/src/registry.dart): a single JSON object at
 * $XDG_RUNTIME_DIR|$XDG_STATE_HOME|~/.local/state + /ironmcp/registry.json, keyed by entry id,
 * each value a {@see RegistryEntry} shape. A Dart server and a PHP server share ONE file.
 *
 * PHP has O_EXCL via fopen(..., 'x'): the open fails (returns false) if the file already exists, an
 * atomic create-or-fail — the same primitive Dart's File.create(exclusive: true) uses.
 */
final class Registry
{
    private readonly string $dir;

    /** @var callable(int):bool */
    private $isPidAlive;

    /**
     * @param string|null            $dir           registry directory; defaults to the XDG path
     * @param (callable(int):bool)|null $isPidAlive  liveness probe; defaults to a POSIX/proc check
     * @param float                  $lockTimeout   seconds to wait for the lock before best-effort proceed
     * @param float                  $staleLockAfter seconds after which a stale lock is stolen
     */
    public function __construct(
        ?string $dir = null,
        ?callable $isPidAlive = null,
        private readonly float $lockTimeout = 3.0,
        private readonly float $staleLockAfter = 30.0,
    ) {
        $this->dir = $dir ?? self::defaultDir();
        $this->isPidAlive = $isPidAlive ?? self::pidAliveDefault(...);
    }

    private function file(): string
    {
        return $this->dir . '/registry.json';
    }

    private function lockFile(): string
    {
        return $this->dir . '/registry.json.lock';
    }

    public static function defaultDir(): string
    {
        $env = getenv();
        $base = $env['XDG_RUNTIME_DIR']
            ?? $env['XDG_STATE_HOME']
            ?? (($env['HOME'] ?? '.') . '/.local/state');

        return $base . '/ironmcp';
    }

    /** Register (or replace) an entry. Locked read-modify-write. */
    public function register(RegistryEntry $entry): void
    {
        $this->withLock(function () use ($entry): void {
            $map = $this->read();
            // toArray() already casts capabilities to an object; casting the entry itself to an
            // object keeps the whole value object-shaped so a rewrite never flips {} to [].
            $map->{$entry->id} = (object) $entry->toArray();
            $this->write($map);
        });
    }

    /** Remove an entry by id. Locked read-modify-write. */
    public function unregister(string $id): void
    {
        $this->withLock(function () use ($id): void {
            $map = $this->read();
            unset($map->{$id});
            $this->write($map);
        });
    }

    /**
     * Live servers, pruning any whose pid is dead (and rewriting the file if it pruned). A
     * hard-killed process is cleaned up lazily on the next reader's scan, since its own unregister
     * never ran (invariant #10).
     *
     * @return list<RegistryEntry>
     */
    public function discover(): array
    {
        $live = [];
        $this->withLock(function () use (&$live): void {
            $map = $this->read();
            $pruned = false;
            foreach (get_object_vars($map) as $key => $raw) {
                if (!is_object($raw)) {
                    unset($map->{$key});
                    $pruned = true;
                    continue;
                }
                $entry = RegistryEntry::fromArray((array) $raw);
                if (($this->isPidAlive)($entry->pid)) {
                    $live[] = $entry;
                } else {
                    unset($map->{$key});
                    $pruned = true;
                }
            }
            if ($pruned) {
                $this->write($map);
            }
        });

        return $live;
    }

    /**
     * Read the registry as an object tree. Decoding to objects (not associative arrays) preserves
     * the JSON distinction between {} and [] across a read-modify-write — critical for cross-kit
     * compatibility, since a Dart consumer reads `capabilities` as a Map and a stray [] would throw.
     */
    private function read(): \stdClass
    {
        $file = $this->file();
        if (!is_file($file)) {
            return new \stdClass();
        }
        $txt = @file_get_contents($file);
        if ($txt === false || trim($txt) === '') {
            return new \stdClass();
        }
        try {
            $decoded = json_decode($txt, false, 512, \JSON_THROW_ON_ERROR);
        } catch (\JsonException) {
            return new \stdClass(); // corrupt/unreadable: start fresh rather than crash
        }

        return $decoded instanceof \stdClass ? $decoded : new \stdClass();
    }

    /**
     * Atomic write: encode to a unique tmp file on the same filesystem, then rename over the target.
     * An empty top-level object encodes as {} (matching Dart), never [].
     */
    private function write(\stdClass $map): void
    {
        $this->ensureDir();
        $json = json_encode($map, \JSON_PRETTY_PRINT | \JSON_UNESCAPED_SLASHES | \JSON_UNESCAPED_UNICODE);
        if ($json === false) {
            $json = '{}';
        }
        $tmp = \sprintf('%s.tmp.%d.%s', $this->file(), getmypid() ?: 0, bin2hex(random_bytes(6)));
        file_put_contents($tmp, $json, \LOCK_EX);
        if (!@rename($tmp, $this->file())) {
            @unlink($tmp);
        }
    }

    /** @param callable():void $body */
    private function withLock(callable $body): void
    {
        $this->ensureDir();
        $lock = $this->lockFile();
        $deadline = microtime(true) + $this->lockTimeout;
        $acquired = false;
        while (true) {
            // fopen(..., 'x') is O_EXCL|O_CREAT: fails (false) if the lock already exists.
            $fh = @fopen($lock, 'x');
            if ($fh !== false) {
                fclose($fh);
                $acquired = true;
                break;
            }
            // A crashed holder can leave a stale lock — steal it past staleLockAfter.
            $mtime = @filemtime($lock);
            if ($mtime !== false && (microtime(true) - $mtime) > $this->staleLockAfter) {
                @unlink($lock);
                continue;
            }
            if (microtime(true) >= $deadline) {
                break; // proceed best-effort
            }
            usleep(5000); // 5ms
        }
        try {
            $body();
        } finally {
            if ($acquired) {
                @unlink($lock);
            }
        }
    }

    private function ensureDir(): void
    {
        if (!is_dir($this->dir)) {
            @mkdir($this->dir, 0o700, true);
        }
    }

    /** Default liveness probe: POSIX kill(0) when available, else /proc, else fail open. */
    private static function pidAliveDefault(int $pid): bool
    {
        if (\function_exists('posix_kill')) {
            if (posix_kill($pid, 0)) {
                return true;
            }
            // EPERM (1) means the process exists but is owned by another user — still alive.
            return \defined('PHP_INT_MAX') && posix_get_last_error() === 1;
        }
        if (is_dir('/proc')) {
            return is_dir("/proc/{$pid}");
        }

        return true; // fail open — never prune a live entry we cannot verify
    }
}
