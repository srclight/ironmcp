"""Baseline: bare v2 (no strict layer) silently DROPS an unknown argument, through a
real client session. This is the bug the port removes; the test documents it."""

import pytest

from tests.v2.harness import build_probe_server, result_text, session_call


@pytest.mark.asyncio
async def test_bare_v2_drops_unknown_argument():
    srv = build_probe_server()
    result = await session_call(srv, "echo", {"a": "x", "typo": "ignored"})
    # No error — the undeclared 'typo' vanishes and the call answers a question nobody asked.
    assert result.is_error is False
    assert "x|default" in result_text(result)


@pytest.mark.asyncio
async def test_bare_v2_zero_arg_tool_drops_extras():
    srv = build_probe_server()
    result = await session_call(srv, "ping", {"typo": 1})
    assert result.is_error is False
    assert "pong" in result_text(result)
