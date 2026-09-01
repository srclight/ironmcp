<?php

declare(strict_types=1);

namespace IronMcp;

use Mcp\Exception\InvalidArgumentException;

/**
 * Constant-time bearer-token check. Fails CLOSED on an empty expected token, and compares in
 * constant time so a timing side channel cannot recover the secret (never a fast `==` on a
 * credential — PHP's hash_equals is the length-safe primitive). The live HTTP wiring — rejecting a
 * request with 401 `WWW-Authenticate: Bearer` — is composed into the transport; this is the pure,
 * testable core. Peer of the Dart `BearerAuth` (kits/dart/lib/src/auth.dart).
 */
final class BearerAuth
{
    private const PREFIX = 'Bearer ';

    public function __construct(public readonly string $expectedToken)
    {
        if ($expectedToken === '') {
            throw new InvalidArgumentException('bearer token must not be empty — fail closed');
        }
    }

    /**
     * True iff [authorizationHeader] is exactly `Bearer <expectedToken>`. A missing/empty/wrong
     * header is rejected. The comparison is constant-time in the token length (invariant #4).
     */
    public function accepts(?string $authorizationHeader): bool
    {
        if ($authorizationHeader === null || $authorizationHeader === '') {
            return false;
        }
        if (!str_starts_with($authorizationHeader, self::PREFIX)) {
            return false;
        }
        $presented = substr($authorizationHeader, \strlen(self::PREFIX));

        // hash_equals is constant-time and length-safe; an empty presented token still fails.
        return hash_equals($this->expectedToken, $presented);
    }
}
