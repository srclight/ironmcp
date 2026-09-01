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
