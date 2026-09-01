<?php

declare(strict_types=1);

namespace IronMcp\Tests;

use IronMcp\StrictArgs;
use Mcp\Capability\Discovery\SchemaValidator;
use PHPUnit\Framework\TestCase;
use Psr\Log\NullLogger;

/**
 * The baseline the corpus must FAIL against: a bare mcp/sdk tool schema is OPEN (reflection
 * omits additionalProperties), so the SDK's own Opis validator ACCEPTS an undeclared argument —
 * the silent drop. Closing the schema (what Harden does) makes that same validator refuse it,
 * naming the key without echoing the value.
 */
final class BaselineDropTest extends TestCase
{
    public function testBareSchemaAcceptsAnExtraArgumentTheSilentDrop(): void
    {
        $validator = new SchemaValidator(new NullLogger());
        $open = ['type' => 'object', 'properties' => ['a' => ['type' => 'string']]];
        $errors = $validator->validateAgainstJsonSchema(['a' => 'x', 'typo' => 'ignored'], $open);
        $this->assertSame([], $errors, 'the SDK accepts the undeclared argument against an open schema');
    }

    public function testClosingTheSchemaMakesTheSdkRefuseTheExtraNamingTheKeyNotTheValue(): void
    {
        $validator = new SchemaValidator(new NullLogger());
        $closed = StrictArgs::stampClosed(['type' => 'object', 'properties' => ['a' => ['type' => 'string']]]);
        $errors = $validator->validateAgainstJsonSchema(['a' => 'x', 'typo' => 'ignored'], $closed);
        $this->assertNotEmpty($errors, 'additionalProperties:false makes the SDK refuse the extra');
        $blob = json_encode($errors, JSON_THROW_ON_ERROR);
        $this->assertStringContainsString('typo', $blob, 'the refusal names the offending key');
        $this->assertStringNotContainsString('ignored', $blob, 'the refusal never echoes the value');
    }
}
