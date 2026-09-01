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

    /**
     * The real-SDK shape: an SDK that normalises an empty `{}` into a stdClass. `properties` given
     * as an empty stdClass is still state 2 (enforced, zero args accepted) — a stray key is refused,
     * and the schema stamps closed. This exercises the `(array)` cast on a stdClass, uncovered before.
     */
    public function testStdClassPropertiesIsIntrospectedAsAZeroArgMap(): void
    {
        $schema = ['type' => 'object', 'properties' => new \stdClass()];
        $this->assertFalse(StrictArgs::check($schema, ['typo' => 1])['ok'], 'empty {} accepts no args');
        $this->assertTrue(StrictArgs::check($schema, [])['ok']);
        $this->assertFalse(StrictArgs::stampClosed($schema)['additionalProperties'], 'still stamps closed');
    }

    /**
     * A stdClass `properties` carrying real fields is introspected as a name map: declared keys pass,
     * an undeclared key is refused. Proves the stdClass path is not merely treated as empty.
     */
    public function testStdClassPropertiesWithFieldsIsANameMap(): void
    {
        $props = new \stdClass();
        $props->a = ['type' => 'string'];
        $props->b = ['type' => 'string'];
        $schema = ['type' => 'object', 'properties' => $props];
        $this->assertTrue(StrictArgs::check($schema, ['a' => 1, 'b' => 2])['ok']);
        $r = StrictArgs::check($schema, ['a' => 1, 'typo' => 2], 'echo');
        $this->assertFalse($r['ok']);
        $this->assertSame(['typo'], $r['unknown']);
    }

    /**
     * Canonical fix #4: a MALFORMED schema whose `properties` is present but NOT an introspectable
     * map — a string, or a populated JSON list — is UNINTROSPECTABLE, hence PERMISSIVE (state 1).
     * A guard that bricks what it cannot read is worse than the bug it prevents, so it must NOT
     * refuse every argument, and it must NOT stamp the malformed schema closed.
     */
    public function testMalformedPropertiesIsTreatedAsPermissive(): void
    {
        $asString = ['type' => 'object', 'properties' => 'oops'];
        $this->assertTrue(StrictArgs::check($asString, ['anything' => 1])['ok'], 'string properties -> permissive');
        $this->assertSame($asString, StrictArgs::stampClosed($asString), 'must not stamp a malformed schema closed');

        $asList = ['type' => 'object', 'properties' => ['a', 'b', 'c']];
        $this->assertTrue(StrictArgs::check($asList, ['whatever' => 1])['ok'], 'list properties -> permissive');
        $this->assertSame($asList, StrictArgs::stampClosed($asList), 'must not stamp a list-properties schema closed');
    }
}
