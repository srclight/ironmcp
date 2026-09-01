<?php

declare(strict_types=1);

namespace IronMcp\Tests;

use IronMcp\BearerAuth;
use IronMcp\HostGuard;
use Mcp\Exception\InvalidArgumentException;
use PHPUnit\Framework\TestCase;

final class AuthTest extends TestCase
{
    // ---- BearerAuth (invariant #4: constant-time compare, 401 on empty/wrong) ----

    public function testAcceptsTheExactBearerToken(): void
    {
        $this->assertTrue((new BearerAuth('s3cret-token'))->accepts('Bearer s3cret-token'));
    }

    public function testRejectsAWrongToken(): void
    {
        $this->assertFalse((new BearerAuth('s3cret-token'))->accepts('Bearer nope'));
    }

    public function testRejectsAMissingEmptyOrMalformedHeader(): void
    {
        $auth = new BearerAuth('s3cret-token');
        $this->assertFalse($auth->accepts(null));
        $this->assertFalse($auth->accepts(''));
        $this->assertFalse($auth->accepts('s3cret-token')); // no Bearer prefix
        $this->assertFalse($auth->accepts('Bearer '));       // empty presented token
    }

    public function testAnEmptyExpectedTokenIsRefusedAtConstruction(): void
    {
        $this->expectException(InvalidArgumentException::class);
        new BearerAuth('');
    }

    public function testATokenThatIsAPrefixOfTheSecretIsRejected(): void
    {
        $this->assertFalse((new BearerAuth('s3cret-token'))->accepts('Bearer s3cret'));
    }

    // ---- HostGuard (DNS-rebinding, default ON — invariant #4) ----

    public function testAcceptsAnAllowedHostWithOrWithoutAPort(): void
    {
        $guard = new HostGuard(['localhost', '127.0.0.1', 'wasabi.local']);
        $this->assertTrue($guard->accepts('localhost'));
        $this->assertTrue($guard->accepts('localhost:8080'));
        $this->assertTrue($guard->accepts('wasabi.local:18888'));
    }

    public function testRejectsARebindingAttackerHostAndANullOrEmptyHost(): void
    {
        $guard = new HostGuard(['localhost', '127.0.0.1', 'wasabi.local']);
        $this->assertFalse($guard->accepts('evil.example.com'));
        $this->assertFalse($guard->accepts('evil.example.com:8080'));
        $this->assertFalse($guard->accepts(null));
        $this->assertFalse($guard->accepts(''));
    }

    public function testPortlessMatchCanBeDisabled(): void
    {
        $strict = new HostGuard(['localhost'], allowPortlessMatch: false);
        $this->assertTrue($strict->accepts('localhost'));
        $this->assertFalse($strict->accepts('localhost:8080'));
    }

    /**
     * HTTP Host is case-insensitive (RFC 7230): a 'LocalHost' or 'LOCALHOST:8080' Host header must
     * match a lower-case 'localhost' allowlist entry, and a mixed-case allowlist entry must match a
     * lower-case header. Exact-case matching (the pre-fix bug) would wrongly reject a legitimate host.
     */
    public function testHostMatchIsCaseInsensitiveBothDirections(): void
    {
        $guard = new HostGuard(['localhost', 'Wasabi.Local']);
        // Header case varies, allowlist is lower — must still match.
        $this->assertTrue($guard->accepts('LocalHost'));
        $this->assertTrue($guard->accepts('LOCALHOST:8080'));
        // Allowlist entry has mixed case, header is lower — must still match (folded on both sides).
        $this->assertTrue($guard->accepts('wasabi.local'));
        $this->assertTrue($guard->accepts('WASABI.LOCAL:18888'));
        // A genuinely different host is still refused regardless of case.
        $this->assertFalse($guard->accepts('EVIL.example.com'));
    }

    /**
     * Gap #13: the guards must actually GATE a request, not merely answer `accepts()` in isolation.
     * The kit's docstrings state the live 401/403 wiring is composed into the transport by the app;
     * here we drive that composition — a request gate that reads the `Host` and `Authorization`
     * headers exactly as an HTTP middleware would, consults both guards, and yields the transport's
     * verdict (403 host / 401 bearer / 200 pass-through). This proves the guards reject a request
     * end-to-end at the header layer, including case variance on the Host header.
     *
     * @param array<string, string> $headers
     */
    private function gate(BearerAuth $auth, HostGuard $host, array $headers): int
    {
        if (!$host->accepts($headers['Host'] ?? null)) {
            return 403; // DNS-rebinding guard rejects before auth is even consulted
        }
        if (!$auth->accepts($headers['Authorization'] ?? null)) {
            return 401; // WWW-Authenticate: Bearer
        }

        return 200;
    }

    public function testGuardsGateARequestOverTheHeaderLayer(): void
    {
        $auth = new BearerAuth('s3cret-token');
        $host = new HostGuard(['localhost']);

        // A legitimate request with a mixed-case Host and the right token passes.
        $this->assertSame(200, $this->gate($auth, $host, [
            'Host' => 'LocalHost:8888',
            'Authorization' => 'Bearer s3cret-token',
        ]));

        // A rebinding attacker's Host is refused with 403 before the token is even checked.
        $this->assertSame(403, $this->gate($auth, $host, [
            'Host' => 'evil.example.com',
            'Authorization' => 'Bearer s3cret-token',
        ]));

        // An allowed Host but a wrong/missing bearer token is refused with 401.
        $this->assertSame(401, $this->gate($auth, $host, [
            'Host' => 'localhost',
            'Authorization' => 'Bearer wrong',
        ]));
        $this->assertSame(401, $this->gate($auth, $host, ['Host' => 'localhost']));
    }
}
