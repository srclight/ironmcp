<?php

declare(strict_types=1);

namespace IronMcp;

/**
 * Lifecycle wrapper for an MCP transport. Binds with a Windows-TIME_WAIT-aware retry, keeps a
 * failed start NON-FATAL (records {@see lastError} instead of throwing), and stops cleanly. The
 * bind/unbind are injected, so the retry logic is unit-testable without opening a real port — and a
 * caller wires the real transport start/stop in.
 *
 * PHP serving is PHP-FPM/ReactPHP-shaped, so the full daemon stays deliberately minimal: this owns
 * the retry policy and the non-fatal contract, not an event loop. Peer of the Dart `IronMcpDaemon`
 * (kits/dart/lib/src/serve.dart): retry only the retryable {@see BindBusyException}; fast-fail every
 * other throwable; never throw out of start.
 */
final class Daemon
{
    /** @var callable():void */
    private $bind;

    /** @var (callable():void)|null */
    private $unbind;

    /** @var (callable(string):void)|null */
    private $onLog;

    private bool $running = false;

    private ?\Throwable $lastError = null;

    /**
     * @param callable():void          $bind       binds the transport; throws {@see BindBusyException} when busy
     * @param (callable():void)|null   $unbind     stops the transport (best-effort)
     * @param int                      $maxRetries bind attempts before giving up (loqu8 used 3)
     * @param float                    $retryDelay seconds between attempts (loqu8 used 2s — Windows TIME_WAIT)
     * @param (callable(string):void)|null $onLog  optional log sink
     */
    public function __construct(
        callable $bind,
        ?callable $unbind = null,
        public readonly int $maxRetries = 3,
        public readonly float $retryDelay = 2.0,
        ?callable $onLog = null,
    ) {
        $this->bind = $bind;
        $this->unbind = $unbind;
        $this->onLog = $onLog;
    }

    public function isRunning(): bool
    {
        return $this->running;
    }

    /** The error from the last failed {@see start}, or null if the last start succeeded. */
    public function lastError(): ?\Throwable
    {
        return $this->lastError;
    }

    /**
     * Start, retrying up to {@see maxRetries} on a {@see BindBusyException} — the TIME_WAIT case
     * where a prior process still holds the port (loqu8 invariant #2). Non-fatal: on final failure
     * it records {@see lastError} and returns false rather than throwing, so a server that cannot
     * bind does not crash the app. A non-busy error fails fast (no retry) and is likewise non-fatal.
     */
    public function start(): bool
    {
        $this->lastError = null;
        for ($attempt = 1; $attempt <= $this->maxRetries; ++$attempt) {
            try {
                ($this->bind)();
                $this->lastError = null; // a retry that ultimately succeeds is not an error
                $this->running = true;

                return true;
            } catch (BindBusyException $e) {
                $this->lastError = $e;
                if ($attempt < $this->maxRetries) {
                    if ($this->onLog !== null) {
                        ($this->onLog)("bind busy (attempt {$attempt}/{$this->maxRetries}): {$e->getMessage()} — retrying in {$this->retryDelay}s");
                    }
                    if ($this->retryDelay > 0) {
                        usleep((int) ($this->retryDelay * 1_000_000));
                    }
                }
            } catch (\Throwable $e) {
                $this->lastError = $e;

                return false; // non-busy: do not retry, do not throw
            }
        }

        return false; // retries exhausted
    }

    /** Stop the transport (best-effort) and clear {@see isRunning}. Safe when not running. */
    public function stop(): void
    {
        try {
            if ($this->unbind !== null) {
                ($this->unbind)();
            }
        } catch (\Throwable $e) {
            // Best-effort: a throwing unbind must NOT propagate out of stop() (the docstring's
            // contract) — record it and, if wired, log it, but always leave the daemon stopped.
            $this->lastError = $e;
            if ($this->onLog !== null) {
                ($this->onLog)("unbind failed (ignored, best-effort stop): {$e->getMessage()}");
            }
        } finally {
            $this->running = false;
        }
    }
}
