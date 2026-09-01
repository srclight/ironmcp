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


# --- The three rich refusal diagnostics (guarantees kept from the v1 kit; the guarantee
# lives in the LIBRARY so every consumer inherits it and none re-tests it). ---


@pytest.mark.asyncio
async def test_refusal_reports_the_accepted_set_back():
    """Refusing without saying what IS accepted leaves the agent guessing. echo accepts a, b."""
    r = await session_call(build_strict_server(), "echo", {"a": "x", "typo": 1})
    text = result_text(r)
    assert r.is_error is True
    assert "accepts: a, b" in text


@pytest.mark.asyncio
async def test_refusal_message_is_bounded_by_the_server_not_the_caller():
    """A caller sending many unknown keys must not reflect an unbounded error back over MCP.
    Only key NAMES are ever echoed, and only the first _MAX_ENUMERATED (10) of them."""
    from ironmcp._messages import _MAX_ENUMERATED

    flood = {f"z{i:03d}": 1 for i in range(_MAX_ENUMERATED + 5)}
    flood["a"] = "x"  # one legitimate arg alongside the flood
    r = await session_call(build_strict_server(), "echo", flood)
    text = result_text(r)
    assert r.is_error is True
    assert f"and {5} more" in text
    assert "z014" not in text  # the 15th unknown key is past the cap, never enumerated


@pytest.mark.asyncio
async def test_a_confusable_argument_name_is_diagnosed_not_just_refused():
    """A fullwidth 'a' (U+FF41) NFKC-normalises to the accepted 'a' -- glyph-identical in most
    fonts. The schema is authoritative for names, so it is refused, but the codepoint is named."""
    r = await session_call(build_strict_server(), "echo", {"ａ": "x"})
    text = result_text(r)
    assert r.is_error is True
    assert "U+FF41" in text
    assert "which IS accepted" in text
