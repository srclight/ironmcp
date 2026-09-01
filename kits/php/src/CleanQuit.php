<?php

declare(strict_types=1);

namespace IronMcp;

/**
 * A fenced, idempotent, ORDERED shutdown scaffold. The steps are app-supplied — an app releases
 * what only it owns, flushes telemetry, stops its MCP server, destroys its window, exits — and
 * ironmcp guarantees they run ONCE, IN ORDER, EACH FENCED so one failure cannot strand the rest.
 * The ORDER is the caller's contract (e.g. flush BEFORE stop, or the final telemetry batch is lost
 * — loqu8 invariant #5); the run-once guard is invariant #6.
 *
 * Peer of the Dart `CleanQuit` (kits/dart/lib/src/quit.dart).
 */
final class CleanQuit
{
    /** @var list<callable():void> */
    private array $steps;

    /** @var (callable(int, \Throwable):void)|null */
    private $onError;

    private bool $done = false;

    /**
     * @param list<callable():void>            $steps
     * @param (callable(int, \Throwable):void)|null $onError called with (index, error) when a step throws; the sequence continues
     */
    public function __construct(array $steps, ?callable $onError = null)
    {
        $this->steps = $steps;
        $this->onError = $onError;
    }

    public function hasRun(): bool
    {
        return $this->done;
    }

    /**
     * Run the sequence once. A second call is a no-op (#6). Each step is fenced; a throwing step is
     * reported via onError and does NOT abort the rest.
     */
    public function run(): void
    {
        if ($this->done) {
            return;
        }
        $this->done = true;
        foreach ($this->steps as $i => $step) {
            try {
                $step();
            } catch (\Throwable $e) {
                if ($this->onError !== null) {
                    ($this->onError)($i, $e);
                }
            }
        }
    }
}
