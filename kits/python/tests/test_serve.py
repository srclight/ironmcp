"""F3 port-retry: retry on OSError is non-fatal and records last_error (#2)."""

import pytest

from ironmcp import PortRetry


@pytest.mark.asyncio
async def test_start_retries_on_oserror_then_succeeds_invariant_2():
    calls = {"n": 0}

    async def bind():
        calls["n"] += 1
        if calls["n"] < 3:
            raise OSError("address already in use")

    d = PortRetry(bind=bind, retry_delay=0.0)
    assert await d.start() is True
    assert calls["n"] == 3
    assert d.is_running is True
    assert d.last_error is None


@pytest.mark.asyncio
async def test_start_gives_up_after_max_retries_non_fatal_sets_last_error():
    calls = {"n": 0}

    async def bind():
        calls["n"] += 1
        raise OSError("busy")

    d = PortRetry(bind=bind, retry_delay=0.0)
    assert await d.start() is False  # does NOT raise
    assert calls["n"] == 3
    assert d.is_running is False
    assert isinstance(d.last_error, OSError)


@pytest.mark.asyncio
async def test_a_non_socket_error_fails_fast_no_retry_and_is_non_fatal():
    calls = {"n": 0}

    async def bind():
        calls["n"] += 1
        raise ValueError("boom")

    d = PortRetry(bind=bind, retry_delay=0.0)
    assert await d.start() is False
    assert calls["n"] == 1
    assert isinstance(d.last_error, ValueError)


@pytest.mark.asyncio
async def test_stop_runs_unbind_and_clears_is_running_safe_when_not_running():
    unbound = {"n": 0}

    async def unbind():
        unbound["n"] += 1

    d = PortRetry(bind=_noop, unbind=unbind, retry_delay=0.0)
    await d.start()
    assert d.is_running is True
    await d.stop()
    assert d.is_running is False
    assert unbound["n"] == 1
    await d.stop()  # no raise when already stopped
    assert d.is_running is False


async def _noop() -> None:
    return None
