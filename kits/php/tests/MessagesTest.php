<?php

declare(strict_types=1);

namespace IronMcp\Tests;

use IronMcp\Messages;
use PHPUnit\Framework\TestCase;

final class MessagesTest extends TestCase
{
    public function testNamesTheKeyAndAcceptedSetAndSaysNothingRan(): void
    {
        $m = Messages::unknownArgs('echo', ['typo'], ['a', 'b']);
        $this->assertStringContainsString('unknown argument(s): typo', $m);
        $this->assertStringContainsString('accepts: a, b', $m);
        $this->assertStringContainsString('Nothing was executed', $m);
    }

    public function testBoundsEnumerationAtTenThenAndNMore(): void
    {
        $unknown = array_map(fn ($i) => sprintf('z%03d', $i), range(0, 14)); // 15 keys
        $m = Messages::unknownArgs('echo', $unknown, ['a']);
        $this->assertStringContainsString('and 5 more', $m);
        $this->assertStringNotContainsString('z014', $m); // 15th key is past the cap of 10
    }

    public function testAcceptedSetIsSorted(): void
    {
        $m = Messages::unknownArgs('echo', ['secret'], ['b', 'a']);
        $this->assertStringContainsString('accepts: a, b', $m);
    }

    public function testEndsWithTheReconnectHint(): void
    {
        $m = Messages::unknownArgs('echo', ['typo'], ['a'], 'check status and reconnect');
        $this->assertStringEndsWith('check status and reconnect.', rtrim($m));
    }

    public function testDiagnosesAnNfkcConfusableKeyByCodepoint(): void
    {
        if (!class_exists('Normalizer')) {
            $this->markTestSkipped('ext-intl (Normalizer) not installed; NFKC diagnosis is verified in CI.');
        }
        $m = Messages::unknownArgs('echo', ["\u{FF41}"], ['a']); // fullwidth 'a' -> NFKC 'a'
        $this->assertStringContainsString('U+FF41', $m);
        $this->assertStringContainsString('which IS accepted', $m);
    }
}
