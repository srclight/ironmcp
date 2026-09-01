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

    /**
     * Gap #16: the exact MAX_ENUMERATED=10 boundary. At exactly 10 unknown keys there is NO
     * "and N more" suffix; at 11 the suffix reads "and 1 more". An off-by-one in the cap would
     * either drop the 10th key or wrongly append a suffix at 10.
     */
    public function testEnumerationBoundaryAtExactlyTenHasNoSuffix(): void
    {
        $ten = array_map(fn ($i) => sprintf('k%02d', $i), range(0, 9)); // exactly 10 keys
        $m = Messages::unknownArgs('echo', $ten, ['a']);
        $this->assertStringNotContainsString('more', $m, 'no suffix at exactly the cap');
        $this->assertStringContainsString('k09', $m, 'the 10th key is still shown');
    }

    public function testEnumerationBoundaryAtElevenSaysAndOneMore(): void
    {
        $eleven = array_map(fn ($i) => sprintf('k%02d', $i), range(0, 10)); // 11 keys
        $m = Messages::unknownArgs('echo', $eleven, ['a']);
        $this->assertStringContainsString('and 1 more', $m);
        $this->assertStringNotContainsString('k10', $m, 'the 11th key is past the cap');
    }

    /**
     * Gap #8: a zero-argument tool's accepted set is empty, so the message must read
     * "accepts: (no arguments)" rather than an empty "accepts: .".
     */
    public function testZeroArgToolSaysNoArguments(): void
    {
        $m = Messages::unknownArgs('ping', ['typo'], []);
        $this->assertStringContainsString('accepts: (no arguments)', $m);
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
