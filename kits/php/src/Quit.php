<?php

declare(strict_types=1);

namespace IronMcp;

/**
 * Clean-quit entry points. {@see replyThenQuit} returns the tool result to the caller NOW and
 * defers the quit to a later tick so the response is written before the endpoint tears down
 * (loqu8 invariant #1). {@see CleanQuit} runs the ordered, fenced, run-once shutdown sequence.
 */
final class Quit
{
    /**
     * Reply-before-quit: hand back a {@see DeferredReply} whose {@see DeferredReply::result} is the
     * value to return to the caller immediately; the transport calls {@see DeferredReply::fire}
     * after the response is flushed to run [quit]. Mirrors Dart's ~300ms grace, but explicit rather
     * than timed since the base PHP SDK has no event loop.
     *
     * @param callable():void $quit
     */
    public static function replyThenQuit(mixed $result, callable $quit): DeferredReply
    {
        return new DeferredReply($result, $quit);
    }
}
