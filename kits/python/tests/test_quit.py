"""F4 clean-quit: ordered + fenced + run-once (#5/#6), reply-before-quit (#1)."""

import asyncio

import pytest

from ironmcp import CleanQuit, reply_then_quit


@pytest.mark.asyncio
async def test_steps_run_in_order():
    order: list[int] = []
    await CleanQuit(
        [
            lambda: _append(order, 1),
            lambda: _append(order, 2),
            lambda: _append(order, 3),
        ]
    ).run()
    assert order == [1, 2, 3]


@pytest.mark.asyncio
async def test_a_throwing_step_does_not_abort_the_rest_invariant_5():
    order: list[int] = []
    errored: list[int] = []
    await CleanQuit(
        [
            lambda: _append(order, 1),
            _boom,
            lambda: _append(order, 3),
        ],
        on_error=lambda i, e: errored.append(i),
    ).run()
    assert order == [1, 3]
    assert errored == [1]  # the throwing step's index


@pytest.mark.asyncio
async def test_second_run_is_a_no_op_idempotent_invariant_6():
    count = {"n": 0}

    async def inc():
        count["n"] += 1

    q = CleanQuit([inc])
    await q.run()
    await q.run()
    assert count["n"] == 1
    assert q.has_run is True


@pytest.mark.asyncio
async def test_reply_then_quit_returns_the_result_before_the_quit_fires_invariant_1():
    fired = asyncio.Event()
    quit_fired = {"v": False}

    async def quit():
        quit_fired["v"] = True
        fired.set()

    r = reply_then_quit("reply", quit, delay=0.0)
    assert r == "reply"
    assert quit_fired["v"] is False  # reply returned first; quit not yet fired
    await asyncio.wait_for(fired.wait(), timeout=1.0)
    assert quit_fired["v"] is True


async def _append(target: list[int], value: int) -> None:
    target.append(value)


async def _boom() -> None:
    raise RuntimeError("boom")
