"""A real MCP server built with the kit, plus an end-to-end check that the guarantee
actually holds over a live client<->server session.

Run inside .venv-v2:  python examples/demo.py
"""

from __future__ import annotations

import anyio
from mcp.client.session import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

from ironmcp import aassert_enforces_v2, health_payload, strict_server


# --- a real server, the way a consumer writes one -------------------------------------
app = strict_server(name="weather-demo", version="0.3.0")


@app.tool()
async def get_forecast(city: str, days: int = 3) -> str:
    """Pretend forecast for a city."""
    return f"{city}: sunny for {days} day(s)"


@app.tool()
async def list_cities() -> str:
    """A zero-argument tool."""
    return "London, Tokyo, Bellingham"


# --- drive it end to end, as a client would -------------------------------------------
async def _call(client, tool, args):
    return await client.call_tool(tool, args)


async def main() -> None:
    print(f"health: {health_payload('weather-demo', '0.3.0')}")

    # 1. the conformance guarantee holds for every tool
    enforced = await aassert_enforces_v2(app)
    print(f"conformance: assert_enforces_v2 -> {enforced} tool(s) enforce a closed contract")

    # 2. a live session: good call works; a typo is REFUSED, not dropped
    ll = app._lowlevel_server
    async with create_client_server_memory_streams() as ((cr, cw), (sr, sw)):
        async with anyio.create_task_group() as tg:
            tg.start_soon(lambda: ll.run(sr, sw, ll.create_initialization_options()))
            async with ClientSession(cr, cw) as client:
                await client.initialize()

                good = await _call(client, "get_forecast", {"city": "Tokyo", "days": 2})
                assert good.is_error is False
                print(f"good call  -> {good.content[0].text!r}")

                typo = await _call(client, "get_forecast", {"city": "Tokyo", "dayz": 2})
                assert typo.is_error is True
                print(f"typo call  -> REFUSED: {typo.content[0].text[:70]}...")

                zero = await _call(client, "list_cities", {"oops": 1})
                assert zero.is_error is True
                print("zero-arg tool with a typo -> REFUSED")

                # the catalog tells the truth
                tools = (await client.list_tools()).tools
                fc = next(t for t in tools if t.name == "get_forecast")
                assert fc.input_schema.get("additionalProperties") is False
                print("advertised schema: additionalProperties == false (advertise == runtime)")
            tg.cancel_scope.cancel()

    print("\nDEMO OK — the kit works end to end.")


if __name__ == "__main__":
    anyio.run(main)
