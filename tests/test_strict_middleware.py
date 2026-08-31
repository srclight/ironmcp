"""StrictArgsMiddleware refuses unknown args (through a real session), honours the
additionalProperties:true opt-out, and lets declared args pass."""

import pytest

from tests.harness import build_strict_server, result_text, session_call


@pytest.mark.asyncio
async def test_unknown_arg_is_refused_not_dropped():
    r = await session_call(build_strict_server(), "echo", {"a": "x", "typo": "ignored"})
    assert r.is_error is True
    text = result_text(r)
    assert "unknown argument(s): typo" in text
    assert "Nothing was executed" in text


@pytest.mark.asyncio
async def test_known_args_pass_through():
    r = await session_call(build_strict_server(), "echo", {"a": "x", "b": "y"})
    assert r.is_error is False
    assert "x|y" in result_text(r)


@pytest.mark.asyncio
async def test_zero_arg_tool_refuses_extras():
    r = await session_call(build_strict_server(), "ping", {"typo": 1})
    assert r.is_error is True


@pytest.mark.asyncio
async def test_additional_properties_true_opts_out():
    """A tool that advertises additionalProperties:true accepts arbitrary keys -- honour it."""
    srv = build_strict_server()
    srv._tool_manager.get_tool("echo").parameters["additionalProperties"] = True
    r = await session_call(srv, "echo", {"a": "x", "anything": 1})
    assert r.is_error is False
