"""The conformance corpus passes a strict server and FIRES against a bare one."""

import pathlib

import pytest

from mcpkit.v2.corpus import run_corpus
from tests.v2.harness import build_probe_server, build_strict_server

CASES = pathlib.Path(__file__).resolve().parents[2] / "conformance" / "cases"


@pytest.mark.asyncio
async def test_strict_server_passes_entire_corpus():
    results = await run_corpus(build_strict_server(), CASES)
    failed = [(r.id, r.detail) for r in results if not r.passed]
    assert not failed, f"corpus failures: {failed}"
    assert len(results) >= 4


@pytest.mark.asyncio
async def test_corpus_fires_against_bare_server():
    results = await run_corpus(build_probe_server(), CASES)
    assert any(not r.passed for r in results), "corpus passed a non-conforming server — it proves nothing"
