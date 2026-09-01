<?php

declare(strict_types=1);

namespace IronMcp\Tests;

use IronMcp\BindBusyException;
use IronMcp\Daemon;
use PHPUnit\Framework\TestCase;

final class ServeTest extends TestCase
{
    /** Invariant #2: start retries on a busy bind, then succeeds; no lastError on success. */
    public function testStartRetriesOnBusyThenSucceeds(): void
    {
        $calls = 0;
        $d = new Daemon(
            bind: function () use (&$calls): void {
                ++$calls;
                if ($calls < 3) {
                    throw new BindBusyException('busy');
                }
            },
            retryDelay: 0.0,
        );
        $this->assertTrue($d->start());
        $this->assertSame(3, $calls);
        $this->assertTrue($d->isRunning());
        $this->assertNull($d->lastError());
    }

    /** Invariant #2: giving up after maxRetries is NON-FATAL and records lastError. */
    public function testStartGivesUpAfterMaxRetriesNonFatal(): void
    {
        $calls = 0;
        $d = new Daemon(
            bind: function () use (&$calls): void {
                ++$calls;
                throw new BindBusyException('busy');
            },
            retryDelay: 0.0,
        );
        $this->assertFalse($d->start()); // does NOT throw
        $this->assertSame(3, $calls);
        $this->assertFalse($d->isRunning());
        $this->assertInstanceOf(BindBusyException::class, $d->lastError());
    }

    /** A non-busy error fails fast (no retry) and is likewise non-fatal. */
    public function testANonBusyErrorFailsFast(): void
    {
        $calls = 0;
        $d = new Daemon(
            bind: function () use (&$calls): void {
                ++$calls;
                throw new \LogicException('boom');
            },
            retryDelay: 0.0,
        );
        $this->assertFalse($d->start());
        $this->assertSame(1, $calls);
        $this->assertInstanceOf(\LogicException::class, $d->lastError());
    }

    public function testStopRunsUnbindAndClearsRunningSafeWhenNotRunning(): void
    {
        $unbound = 0;
        $d = new Daemon(
            bind: static function (): void {},
            unbind: static function () use (&$unbound): void { ++$unbound; },
            retryDelay: 0.0,
        );
        $d->start();
        $this->assertTrue($d->isRunning());
        $d->stop();
        $this->assertFalse($d->isRunning());
        $this->assertSame(1, $unbound);
        $d->stop(); // no throw when already stopped
        $this->assertFalse($d->isRunning());
    }

    /**
     * stop() is best-effort (its docstring): a throwing unbind must NOT propagate out of stop().
     * The daemon must still end up stopped, the error is captured, and a wired log sink is told.
     */
    public function testStopIsBestEffortWhenUnbindThrows(): void
    {
        $logged = [];
        $d = new Daemon(
            bind: static function (): void {},
            unbind: static function (): void { throw new \RuntimeException('unbind exploded'); },
            retryDelay: 0.0,
            onLog: static function (string $m) use (&$logged): void { $logged[] = $m; },
        );
        $d->start();
        $this->assertTrue($d->isRunning());

        $d->stop(); // must not throw despite the throwing unbind

        $this->assertFalse($d->isRunning(), 'a throwing unbind must still leave the daemon stopped');
        $this->assertInstanceOf(\RuntimeException::class, $d->lastError());
        $this->assertNotEmpty($logged, 'the ignored unbind failure is logged when a sink is wired');
    }
}
