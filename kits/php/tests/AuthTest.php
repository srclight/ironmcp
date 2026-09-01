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
}
