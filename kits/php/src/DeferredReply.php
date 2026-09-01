<?php

declare(strict_types=1);

namespace IronMcp;

/**
 * The carrier for reply-before-quit. Holds the tool [result] to hand the caller NOW and a pending
 * [quit] to run LATER — after the transport has written the response. The synchronous PHP peer of
 * Dart's `Timer(delay, quit); return result;` (kits/dart/lib/src/quit.dart): PHP has no event loop
 * in the base SDK, so instead of a timer the transport reads {@see result}, flushes the HTTP
 * response, then calls {@see fire}. Quitting inside the handler drops the reply and reads as a
 * failed tool call (loqu8 invariant #1); this keeps the reply strictly before the teardown.
 */
final class DeferredReply
{
    /** @var callable():void */
    private $quit;

    private bool $fired = false;

    /** @param callable():void $quit */
    public function __construct(public readonly mixed $result, callable $quit)
    {
        $this->quit = $quit;
    }

    /** Run the deferred quit exactly once. A second call is a no-op. */
    public function fire(): void
    {
        if ($this->fired) {
            return;
        }
        $this->fired = true;
        ($this->quit)();
    }

    public function fired(): bool
    {
        return $this->fired;
    }
}
