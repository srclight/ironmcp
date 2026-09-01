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
            $set[$h] = true;
        }
        $this->allowedHosts = $set;
    }

    /** True iff [hostHeader] is allowed. A null/empty host is rejected. */
    public function accepts(?string $hostHeader): bool
    {
        if ($hostHeader === null || $hostHeader === '') {
            return false;
        }
        if (isset($this->allowedHosts[$hostHeader])) {
            return true;
        }
        if ($this->allowPortlessMatch) {
            $portless = explode(':', $hostHeader, 2)[0];
            if (isset($this->allowedHosts[$portless])) {
                return true;
            }
        }

        return false;
    }
}
