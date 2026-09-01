<?php

declare(strict_types=1);

namespace IronMcp\Tests;

use IronMcp\Corpus;
use PHPUnit\Framework\TestCase;

final class CorpusTest extends TestCase
{
    /** The corpus lives at the monorepo root (kits/php/tests -> ../../../conformance) or, in the
     *  read-only split repo, vendored at the package root (tests -> ../conformance). Resolve either. */
    private static function casesDir(): string
    {
        foreach ([__DIR__ . '/../../../conformance/cases', __DIR__ . '/../conformance/cases'] as $dir) {
            if (is_dir($dir)) {
                return $dir;
            }
        }
        throw new \RuntimeException('conformance/cases not found (monorepo or split layout)');
    }

    public function testAHardenedServerPassesEveryCase(): void
    {
        $passed = Corpus::assertEnforces(Corpus::hardenedDriver(), self::casesDir());
        $this->assertGreaterThanOrEqual(5, $passed);
    }

    public function testABareServerFailsTheCorpus(): void
    {
        $this->expectException(\RuntimeException::class);
        Corpus::assertEnforces(Corpus::bareDriver(), self::casesDir());
    }
}
