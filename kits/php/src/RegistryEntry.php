<?php

declare(strict_types=1);

namespace IronMcp;

/**
 * A live ironmcp server's registration. Language-neutral JSON (snake_case), so a Dart iCE, a Python
 * *light server, a Node scarlight and a PHP server all read and write the SAME discovery fabric.
 * Deliberately carries no hand-kept tool list — a consumer enumerates a server's tools via
 * tools/list on its port (loqu8 invariant #3: the list that drifted from 6 to 66).
 *
 * The on-disk shape is byte-identical to the Dart `IronMcpEntry.toJson`
 * (kits/dart/lib/src/registry.dart): the SAME field names, the SAME snake_case (code_sha,
 * started_at), the SAME omit-when-null optionals, and started_at as an ISO-8601 UTC string with
 * milliseconds and a trailing Z.
 */
final class RegistryEntry
{
    public readonly string $startedAt;

    /** @var array<string, mixed> */
    public readonly array $capabilities;

    /**
     * @param array<string, mixed>|null $capabilities
     * @param string|null               $startedAt    ISO-8601 UTC; defaults to now
     */
    public function __construct(
        public readonly string $id,
        public readonly string $namespace,
        public readonly int $pid,
        public readonly ?string $host = null,
        public readonly ?int $port = null,
        public readonly ?string $transport = null,
        public readonly ?string $version = null,
        public readonly ?string $codeSha = null,
        ?array $capabilities = null,
        ?string $startedAt = null,
    ) {
        $this->capabilities = $capabilities ?? [];
        $this->startedAt = $startedAt ?? self::nowIso();
    }

    /**
     * Serialize to the shared cross-kit shape. Field ORDER and null-omission match Dart exactly.
     *
     * @return array<string, mixed>
     */
    public function toArray(): array
    {
        $out = [
            'id' => $this->id,
            'namespace' => $this->namespace,
            'pid' => $this->pid,
        ];
        if ($this->host !== null) {
            $out['host'] = $this->host;
        }
        if ($this->port !== null) {
            $out['port'] = $this->port;
        }
        if ($this->transport !== null) {
            $out['transport'] = $this->transport;
        }
        if ($this->version !== null) {
            $out['version'] = $this->version;
        }
        if ($this->codeSha !== null) {
            $out['code_sha'] = $this->codeSha;
        }
        $out['capabilities'] = (object) $this->capabilities;
        $out['started_at'] = $this->startedAt;

        return $out;
    }

    /**
     * @param array<string, mixed> $j
     */
    public static function fromArray(array $j): self
    {
        $caps = $j['capabilities'] ?? null;

        return new self(
            id: (string) $j['id'],
            namespace: (string) $j['namespace'],
            pid: (int) $j['pid'],
            host: isset($j['host']) ? (string) $j['host'] : null,
            port: isset($j['port']) ? (int) $j['port'] : null,
            transport: isset($j['transport']) ? (string) $j['transport'] : null,
            version: isset($j['version']) ? (string) $j['version'] : null,
            codeSha: isset($j['code_sha']) ? (string) $j['code_sha'] : null,
            capabilities: is_array($caps) ? $caps : ((array) ($caps ?? [])),
            startedAt: isset($j['started_at']) ? (string) $j['started_at'] : null,
        );
    }

    /** ISO-8601 UTC with milliseconds + Z, matching Dart's DateTime.toUtc().toIso8601String(). */
    private static function nowIso(): string
    {
        return (new \DateTimeImmutable('now', new \DateTimeZone('UTC')))->format('Y-m-d\TH:i:s.v\Z');
    }
}
