"""The seam check must FAIL LOUDLY, and must be proven to fail.

A guard nobody has seen fire is a guard nobody knows works -- established the hard way on
2026-08-29, when a skip-guard appeared broken because a shell pipeline swallowed its output.
"""

import pytest

from mcpkit import SeamError, verify_seams


def test_seams_pass_against_the_installed_sdk():
    verify_seams()   # must not raise on a supported SDK


def test_a_missing_seam_raises_rather_than_degrading(monkeypatch):
    """The whole point: silently serving without validation is worse than refusing to start."""
    import mcp.server.fastmcp.tools.base as base

    monkeypatch.setattr(base.Tool, "model_fields", {}, raising=False)
    with pytest.raises(SeamError) as e:
        verify_seams()
    msg = str(e.value)
    assert "Tool.parameters" in msg          # names what moved
    assert "last known good" in msg          # tells you what to pin
    assert "REFUSING TO IMPORT" in msg       # states the policy, not just the fact
