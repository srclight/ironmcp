<?php

declare(strict_types=1);

namespace IronMcp\Tests;

use IronMcp\CleanQuit;
use IronMcp\Quit;
use PHPUnit\Framework\TestCase;

final class QuitTest extends TestCase
{
    public function testStepsRunInOrder(): void
    {
        $order = [];
        (new CleanQuit([
            static function () use (&$order): void { $order[] = 1; },
            static function () use (&$order): void { $order[] = 2; },
            static function () use (&$order): void { $order[] = 3; },
        ]))->run();
        $this->assertSame([1, 2, 3], $order);
    }

    /** Invariant #5: a throwing step is fenced and does NOT abort the rest. */
    public function testAThrowingStepDoesNotAbortTheRest(): void
    {
        $order = [];
        $errored = [];
        (new CleanQuit(
            [
                static function () use (&$order): void { $order[] = 1; },
                static function (): void { throw new \RuntimeException('boom'); },
                static function () use (&$order): void { $order[] = 3; },
            ],
            static function (int $i, \Throwable $e) use (&$errored): void { $errored[] = $i; },
        ))->run();
        $this->assertSame([1, 3], $order);
        $this->assertSame([1], $errored); // the throwing step's index
    }

    /** Invariant #6: a second run is a no-op (idempotent). */
    public function testSecondRunIsANoOp(): void
    {
        $count = 0;
        $q = new CleanQuit([static function () use (&$count): void { ++$count; }]);
        $q->run();
        $q->run();
        $this->assertSame(1, $count);
        $this->assertTrue($q->hasRun());
    }

    /** Invariant #1: replyThenQuit hands back the result BEFORE the quit fires. */
    public function testReplyThenQuitReturnsTheResultBeforeTheQuitFires(): void
    {
        $quitFired = false;
        $deferred = Quit::replyThenQuit('reply', function () use (&$quitFired): void { $quitFired = true; });

        $this->assertSame('reply', $deferred->result);
        $this->assertFalse($quitFired);   // reply available first; quit not yet fired
        $this->assertFalse($deferred->fired());

        $deferred->fire();
        $this->assertTrue($quitFired);
        $this->assertTrue($deferred->fired());

        // fire is idempotent: a second fire does not re-run the quit.
        $count = 0;
        $d2 = Quit::replyThenQuit(1, function () use (&$count): void { ++$count; });
        $d2->fire();
        $d2->fire();
        $this->assertSame(1, $count);
    }
}
