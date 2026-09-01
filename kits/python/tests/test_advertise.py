"""The strict server advertises additionalProperties:false (advertisement == runtime);
a bare server advertises nothing (the silent catalog the guard exists to close)."""

import pytest

from tests.harness import build_probe_server, build_strict_server, session_list_tools


@pytest.mark.asyncio
async def test_strict_server_advertises_closed():
    tools = await session_list_tools(build_strict_server())
    echo = next(t for t in tools if t.name == "echo")
    assert echo.input_schema.get("additionalProperties") is False


@pytest.mark.asyncio
async def test_bare_server_advertises_nothing():
    tools = await session_list_tools(build_probe_server())
    echo = next(t for t in tools if t.name == "echo")
    assert echo.input_schema.get("additionalProperties") is None
