<?php

declare(strict_types=1);

namespace IronMcp\Tests;

use IronMcp\StrictArgs;
use PHPUnit\Framework\TestCase;

final class StrictArgsTest extends TestCase
{
    private const WITH_PROPS = ['type' => 'object', 'properties' => ['a' => [], 'b' => []]];
    private const ZERO_ARG = ['type' => 'object', 'properties' => []];

    public function testState2UnknownKeyRefused(): void
    {
        $r = StrictArgs::check(self::WITH_PROPS, ['a' => 1, 'typo' => 2], 'echo');
        $this->assertFalse($r['ok']);
        $this->assertSame(['typo'], $r['unknown']);
        $this->assertStringContainsString('unknown argument', $r['message']);
    }

    public function testState2KnownKeysOk(): void
    {
        $this->assertTrue(StrictArgs::check(self::WITH_PROPS, ['a' => 1, 'b' => 2])['ok']);
    }

    public function testState2ZeroArgToolRefusesExtras(): void
    {
        $this->assertFalse(StrictArgs::check(self::ZERO_ARG, ['typo' => 1])['ok']);
    }

    public function testState1NoPropertiesIsPermissive(): void
    {
        $this->assertTrue(StrictArgs::check(['type' => 'object'], ['whatever' => 1])['ok']);
    }

    public function testState3AdditionalPropertiesTrueOptsOut(): void
    {
        $schema = ['type' => 'object', 'properties' => ['a' => []], 'additionalProperties' => true];
        $this->assertTrue(StrictArgs::check($schema, ['a' => 1, 'x' => 2])['ok']);
    }

    public function testNullSchemaIsPermissive(): void
    {
        $this->assertTrue(StrictArgs::check(null, ['x' => 1])['ok']);
    }

    public function testStampClosedStampsWhenEnforced(): void
    {
        $this->assertFalse(StrictArgs::stampClosed(self::WITH_PROPS)['additionalProperties']);
        $this->assertFalse(StrictArgs::stampClosed(self::ZERO_ARG)['additionalProperties']);
    }

    public function testStampClosedLeavesOptedOpenAndUnintrospectableAlone(): void
    {
        $open = ['type' => 'object', 'properties' => ['a' => []], 'additionalProperties' => true];
        $this->assertSame($open, StrictArgs::stampClosed($open));
        $bare = ['type' => 'object'];
        $this->assertSame($bare, StrictArgs::stampClosed($bare));
    }
}
