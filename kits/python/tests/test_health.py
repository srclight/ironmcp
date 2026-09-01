"""code_sha never raises; health_payload is honest and complete."""

from ironmcp.health import code_sha, health_payload


def test_code_sha_returns_str_and_never_raises():
    s = code_sha()
    assert isinstance(s, str) and s  # a value (sha or "unknown"), never empty, never an exception


def test_health_payload_shape():
    p = health_payload("myserver", "1.2.3")
    assert p["status"] == "ok"
    assert p["name"] == "myserver"
    assert p["version"] == "1.2.3"
    assert isinstance(p["code_sha"], str) and p["code_sha"]
    assert isinstance(p["mcp_sdk"], str) and p["mcp_sdk"]


def test_code_sha_falls_back_to_unknown_when_git_absent(monkeypatch):
    """code_sha never raises: a git failure (not a repo / git missing) reports 'unknown',
    never a crash and never a stale value dressed as current."""
    import ironmcp.health as health

    def _boom(*_a, **_k):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(health.subprocess, "check_output", _boom)
    assert health.code_sha() == "unknown"


def test_code_sha_reports_unknown_on_empty_git_output(monkeypatch):
    import ironmcp.health as health

    monkeypatch.setattr(health.subprocess, "check_output", lambda *a, **k: "   \n")
    assert health.code_sha() == "unknown"
