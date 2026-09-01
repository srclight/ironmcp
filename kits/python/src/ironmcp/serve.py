"""A non-fatal port-retry helper for the serve path.

Python already has a dominant serving stack (FastMCP / ``streamable_http_app`` + uvicorn),
wired in :mod:`ironmcp.http`. This is NOT a competing framework — it is the one lifecycle
concern that stack does not handle: a bind that races a prior process still holding the port
(the Windows TIME_WAIT case). It wraps an INJECTED bind/unbind so the retry logic is
unit-testable without opening a real socket, and a caller passes uvicorn's start/stop in.

A failed start is NON-FATAL: it records :attr:`last_error` and returns ``False`` rather than
throwing, so a server that cannot bind does not crash the app (loqu8 invariant #2). Ported
from ``kits/dart/lib/src/serve.dart``; ``SocketException`` maps to Python's ``OSError``.
"""

from __future__ import annotations

from typing import Awaitable, Callable, Optional

__all__ = ["PortRetry"]

_Bind = Callable[[], Awaitable[None]]


class PortRetry:
    """Bind with a TIME_WAIT-aware retry; keep a failed start non-fatal; stop cleanly."""

    def __init__(
        self,
        *,
        bind: _Bind,
        unbind: Optional[_Bind] = None,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._bind = bind
        self._unbind = unbind
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._on_log = on_log
        self._running = False
        self._last_error: Optional[BaseException] = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def last_error(self) -> Optional[BaseException]:
        """The error from the last failed :meth:`start`, or ``None`` if the last start
        succeeded (or start was never called)."""
        return self._last_error

    async def start(self) -> bool:
        """Start, retrying up to :attr:`max_retries` on ``OSError`` — the TIME_WAIT case
        where a prior process still holds the port (invariant #2). Non-fatal: on final
        failure it records :attr:`last_error` and returns ``False`` rather than throwing. A
        non-``OSError`` fails fast (no retry) and is likewise non-fatal."""
        import asyncio

        self._last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                await self._bind()
                self._last_error = None  # a retry that ultimately succeeds is not an error
                self._running = True
                return True
            except OSError as e:
                self._last_error = e
                if attempt < self.max_retries:
                    if self._on_log:
                        self._on_log(
                            f"bind busy (attempt {attempt}/{self.max_retries}): {e} — "
                            f"retrying in {self.retry_delay}s"
                        )
                    if self.retry_delay:
                        await asyncio.sleep(self.retry_delay)
            except Exception as e:  # noqa: BLE001
                self._last_error = e
                return False  # non-socket: do not retry, do not throw
        return False  # retries exhausted

    async def stop(self) -> None:
        """Stop the transport (best-effort) and clear :attr:`is_running`. Safe when not
        running."""
        try:
            if self._unbind is not None:
                await self._unbind()
        finally:
            self._running = False
