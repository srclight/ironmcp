<?php

declare(strict_types=1);

namespace IronMcp\Tests;

use IronMcp\Corpus;
use PHPUnit\Framework\TestCase;

final class CorpusTest extends TestCase
{
    // tests/ -> kits/php -> kits -> repo root, where the language-neutral corpus lives.
    private const CASES = __DIR__ . '/../../../conformance/cases';

    public function testAHardenedServerPassesEveryCase(): void
    {
        $passed = Corpus::assertEnforces(Corpus::hardenedDriver(), self::CASES);
        $this->assertGreaterThanOrEqual(5, $passed);
    }

    public function testABareServerFailsTheCorpus(): void
    {
        $this->expectException(\RuntimeException::class);
        Corpus::assertEnforces(Corpus::bareDriver(), self::CASES);
    }
}
