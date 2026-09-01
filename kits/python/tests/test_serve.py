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


@pytest.mark.asyncio
async def test_on_log_callback_fires_between_retries():
    """The on_log hook is invoked on each retriable failure with a human message naming the
    attempt count."""
    logs: list[str] = []
    calls = {"n": 0}

    async def bind():
        calls["n"] += 1
        if calls["n"] < 2:
            raise OSError("busy")

    d = PortRetry(bind=bind, retry_delay=0.0, on_log=logs.append)
    assert await d.start() is True
    assert logs and "attempt 1/3" in logs[0]


@pytest.mark.asyncio
async def test_retry_delay_sleep_path_is_exercised(monkeypatch):
    """A non-zero retry_delay actually reaches asyncio.sleep with that value (the sleep branch,
    bypassed everywhere else by delay=0.0)."""
    import asyncio

    slept: list[float] = []

    async def fake_sleep(d):
        slept.append(d)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    calls = {"n": 0}

    async def bind():
        calls["n"] += 1
        if calls["n"] < 2:
            raise OSError("busy")

    d = PortRetry(bind=bind, retry_delay=2.0)
    assert await d.start() is True
    assert slept == [2.0]


@pytest.mark.asyncio
async def test_max_retries_one_makes_a_single_attempt_no_loop():
    """max_retries=1 is the no-retry boundary: exactly one bind attempt, no sleep/log, non-fatal."""
    calls = {"n": 0}

    async def bind():
        calls["n"] += 1
        raise OSError("busy")

    d = PortRetry(bind=bind, max_retries=1, retry_delay=0.0)
    assert await d.start() is False
    assert calls["n"] == 1
    assert isinstance(d.last_error, OSError)


def test_last_error_is_none_before_start_is_ever_called():
    d = PortRetry(bind=_noop, retry_delay=0.0)
    assert d.last_error is None
    assert d.is_running is False
