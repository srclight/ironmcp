"""A fenced, idempotent, ORDERED shutdown scaffold + reply-before-quit helper.

The steps are app-supplied — an app releases what only it owns, flushes telemetry, stops
its MCP server, destroys its window, exits — and ironmcp guarantees they run **once, in
order, each fenced** so one failure cannot strand the rest. The ORDER is the caller's
contract (e.g. flush BEFORE stop, or the final telemetry batch is lost — loqu8 invariant
#5); the run-once guard is invariant #6.

Ported from ``kits/dart/lib/src/quit.dart``. Async, since a Python MCP handler is async.
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Optional, TypeVar

__all__ = ["CleanQuit", "reply_then_quit"]

_Step = Callable[[], Awaitable[None]]
T = TypeVar("T")


class CleanQuit:
    """Run app-supplied shutdown steps once, in order, each fenced."""

    def __init__(
        self,
        steps: list[_Step],
        *,
        on_error: Optional[Callable[[int, Exception], None]] = None,
    ) -> None:
        self._steps = list(steps)
        self._on_error = on_error
        self._done = False

    @property
    def has_run(self) -> bool:
        return self._done

    async def run(self) -> None:
        """Run the sequence once. A second call is a no-op (#6). Each step is fenced; a
        throwing step is reported via ``on_error`` and does NOT abort the rest (#5)."""
        if self._done:
            return
        self._done = True
        for i, step in enumerate(self._steps):
            try:
                await step()
            except Exception as e:  # noqa: BLE001 - fencing is the point
                # The error HANDLER is itself fenced: a throwing on_error must NOT abort the
                # remaining shutdown steps (#5). A step failing is expected; a reporting hook
                # that also fails cannot be allowed to strand telemetry-flush / window-destroy.
                if self._on_error is not None:
                    try:
                        self._on_error(i, e)
                    except Exception:  # noqa: BLE001 - the handler does not get to break the chain
                        pass


def reply_then_quit(
    result: T,
    quit: Callable[[], Awaitable[None]],
    *,
    delay: float = 0.3,
) -> T:
    """Return ``result`` to the caller NOW, then run ``quit`` on a later tick.

    So the HTTP response is written before the endpoint tears down (loqu8 invariant #1 —
    quitting inside the handler drops the reply and reads as a failed tool call). ``delay``
    mirrors loqu8's ~300 ms grace. Requires a running event loop.
    """
    loop = asyncio.get_event_loop()

    def _fire() -> None:
        loop.create_task(quit())

    loop.call_later(delay, _fire)
    return result
