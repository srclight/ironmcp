"""assert_enforces_v2 must REJECT a bare server (advertises no additionalProperties -->
a silent catalog) and PASS a strict one. A conformance check never watched to fire is theatre."""

import pytest

from mcpkit.v2.conformance import aassert_enforces_v2
from tests.v2.harness import build_probe_server, build_strict_server


@pytest.mark.asyncio
async def test_fires_against_bare_server():
    with pytest.raises(AssertionError):
        await aassert_enforces_v2(build_probe_server())


@pytest.mark.asyncio
async def test_passes_strict_server():
    n = await aassert_enforces_v2(build_strict_server())
    assert n >= 1
