<?php

declare(strict_types=1);

namespace IronMcp;

/**
 * DNS-rebinding / host-allowlist guard. Posture is ON by default: a request whose `Host` header is
 * not in [allowedHosts] is rejected. loqu8 bound 0.0.0.0 with rebinding OFF while a comment falsely
 * claimed it was on — this defaults it ON (invariant #4). Give it the hosts the server legitimately
 * answers as (add the WSL/LAN name/IP + localhost when 0.0.0.0-bound, so WSL reach still works while
 * a rebinding attacker's `Host` is refused). Peer of the Dart `HostGuard` (kits/dart/lib/src/auth.dart).
 */
final class HostGuard
{
    /** @var array<string, true> */
    private readonly array $allowedHosts;

    /**
     * @param iterable<string> $allowedHosts
     */
    public function __construct(iterable $allowedHosts, private readonly bool $allowPortlessMatch = true)
    {
        $set = [];
        foreach ($allowedHosts as $h) {
            // HTTP Host is case-insensitive (RFC 7230 §2.7.3 / §5.4): fold to lower-case so a
            // 'Localhost' allowlist entry still matches a 'localhost' Host header and vice versa.
            $set[strtolower($h)] = true;
        }
        $this->allowedHosts = $set;
    }

    /** True iff [hostHeader] is allowed. A null/empty host is rejected. Matching is case-insensitive. */
    public function accepts(?string $hostHeader): bool
    {
        if ($hostHeader === null || $hostHeader === '') {
            return false;
        }
        $host = strtolower($hostHeader);
        if (isset($this->allowedHosts[$host])) {
            return true;
        }
        if ($this->allowPortlessMatch) {
            $portless = self::stripPort($host);
            if (isset($this->allowedHosts[$portless])) {
                return true;
            }
        }

        return false;
    }

    /**
     * Strip a trailing `:port` from a Host header. A bracketed IPv6 literal ("[::1]" or "[::1]:8080")
     * contains colons inside the brackets, so the port — if present — begins only AFTER the closing
     * "]"; a naive split on the first ":" would truncate "[::1]:8080" to "[" and break the match.
     * A plain host/IPv4 keeps the split-on-first-colon behaviour.
     */
    private static function stripPort(string $host): string
    {
        if (str_starts_with($host, '[')) {
            $close = strpos($host, ']');
            if ($close !== false) {
                return substr($host, 0, $close + 1); // "[::1]" — brackets kept, port dropped
            }

            return $host; // malformed (no closing bracket): leave as-is, it will simply not match
        }

        return explode(':', $host, 2)[0];
    }
}
