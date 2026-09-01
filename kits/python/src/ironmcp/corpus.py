"""Run the language-neutral conformance corpus against a server.

The corpus in ``conformance/cases/*.json`` is owned by no language. This runner is the
first of N: any ironmcp kit, in any language, reimplements a runner that reads the same
JSON and drives its own server. A kit conforms when every case passes.

Case schema::

    { "id": str, "description": str, "tool": str, "arguments": {...},
      "expect": "refuse" | "accept",
      "expect_message_contains"?: [str],   # substrings the refusal MUST contain
      "expect_message_excludes"?: [str] }  # substrings it MUST NOT contain (e.g. values)

Drives a real client<->server session (MCPServer.call_tool bypasses middleware).
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass
from typing import Any

import anyio
from mcp.client.session import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

__all__ = ["Result", "load_cases", "run_corpus"]


@dataclass
class Result:
    id: str
    passed: bool
    detail: str = ""


def load_cases(cases_dir: str | pathlib.Path) -> list[dict[str, Any]]:
    return [json.loads(p.read_text()) for p in sorted(pathlib.Path(cases_dir).glob("*.json"))]


def _check(case: dict[str, Any], is_error: bool, text: str, structured: Any = None) -> Result:
    ok = is_error == (case["expect"] == "refuse")
    for s in case.get("expect_message_contains", []):
        ok = ok and (s in text)
    for s in case.get("expect_message_excludes", []):
        ok = ok and (s not in text)
    # expect_structured: the refusal must carry machine-readable structuredContent.ironmcp
    # whose named fields CONTAIN the expected keys (an agent parses it, not the prose).
    exp = case.get("expect_structured")
    if exp is not None:
        iron = (structured or {}).get("ironmcp") if isinstance(structured, dict) else None
        for field, expected in exp.items():
            got = (iron or {}).get(field) if isinstance(iron, dict) else None
            ok = ok and isinstance(got, list) and all(item in got for item in expected)
    detail = "" if ok else f"expect={case['expect']} is_error={is_error} text={text[:140]!r} structured={structured}"
    return Result(case["id"], ok, detail)


async def run_corpus(server: Any, cases_dir: str | pathlib.Path) -> list[Result]:
    cases = load_cases(cases_dir)
    ll = server._lowlevel_server
    results: list[Result] = []
    async with create_client_server_memory_streams() as ((cr, cw), (sr, sw)):
        async with anyio.create_task_group() as tg:
            tg.start_soon(lambda: ll.run(sr, sw, ll.create_initialization_options()))
            async with ClientSession(cr, cw) as client:
                await client.initialize()
                for case in cases:
                    result = await client.call_tool(case["tool"], case["arguments"])
                    is_error = bool(getattr(result, "is_error", False))
                    text = " ".join(getattr(x, "text", "") for x in (result.content or []))
                    structured = getattr(result, "structured_content", None)
                    results.append(_check(case, is_error, text, structured))
            tg.cancel_scope.cancel()
    return results
