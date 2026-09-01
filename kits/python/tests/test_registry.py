"""F5 registry: concurrent register loses nothing (#9), dead-pid prune (#10), NO tool
list (#3), and the on-disk format byte-compatible with the Dart kit."""

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest

from ironmcp import IronMcpEntry, IronMcpRegistry

# The ONE canonical registry timestamp every kit must emit: ISO-8601 UTC, exactly three
# fractional (millisecond) digits, trailing Z. Byte-identical to JS Date.toISOString().
_CANONICAL_STARTED_AT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


@pytest.fixture
def reg_dir(tmp_path):
    return str(tmp_path / "ironmcp")


def test_concurrent_registers_do_not_lose_an_entry_lock_closes_toctou_9(reg_dir):
    reg = IronMcpRegistry(dir=reg_dir, is_pid_alive=lambda _p: True)
    entries = [
        IronMcpEntry(id=i, namespace="test", pid=n)
        for i, n in [("a", 1), ("b", 2), ("c", 3), ("d", 4)]
    ]
    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(reg.register, entries))
    live = reg.discover()
    assert {e.id for e in live} == {"a", "b", "c", "d"}


def test_discover_prunes_a_dead_pid_and_rewrites_lazy_gc_10(reg_dir):
    reg = IronMcpRegistry(dir=reg_dir, is_pid_alive=lambda pid: pid != 2)
    reg.register(IronMcpEntry(id="a", namespace="test", pid=1))
    reg.register(IronMcpEntry(id="b", namespace="test", pid=2))  # dead
    assert {e.id for e in reg.discover()} == {"a"}
    # rewritten: a second discover still only sees the live one
    assert {e.id for e in reg.discover()} == {"a"}


def test_unregister_removes_an_entry(reg_dir):
    reg = IronMcpRegistry(dir=reg_dir, is_pid_alive=lambda _p: True)
    reg.register(IronMcpEntry(id="a", namespace="test", pid=1))
    reg.unregister("a")
    assert reg.discover() == []


def test_entry_json_is_language_neutral_and_carries_no_tool_list_3():
    j = IronMcpEntry(
        id="x",
        namespace="ns",
        pid=9,
        host="127.0.0.1",
        port=8080,
        transport="http",
        version="1.0",
        code_sha="abc123",
        capabilities={"tools": {}},
    ).to_json()
    assert j["code_sha"] == "abc123"
    assert isinstance(j["started_at"], str)
    assert "tools" not in j  # honesty: no drifting count at the top level
    e = IronMcpEntry.from_json(j)
    assert e.id == "x"
    assert e.port == 8080
    assert e.transport == "http"


def test_on_disk_file_is_keyed_by_entry_id_matching_dart(reg_dir):
    """The Dart registry stores a FLAT object keyed by entry-id (map[entry.id] =
    entry.toJson()). A Python-written file a Dart server reads must have that exact
    shape, snake_case fields and all."""
    reg = IronMcpRegistry(dir=reg_dir, is_pid_alive=lambda _p: True)
    reg.register(
        IronMcpEntry(
            id="srv-1",
            namespace="loqu8",
            pid=1234,
            host="127.0.0.1",
            port=8888,
            transport="streamable-http",
            version="2.0",
            code_sha="deadbee",
            capabilities={"strict_args": True},
        )
    )
    with open(os.path.join(reg_dir, "registry.json"), encoding="utf-8") as f:
        raw = json.load(f)
    assert set(raw.keys()) == {"srv-1"}  # keyed by entry-id, flat
    entry = raw["srv-1"]
    # snake_case wire keys, exactly the Dart set
    assert entry["code_sha"] == "deadbee"
    assert entry["started_at"]
    assert entry["capabilities"] == {"strict_args": True}
    assert "tools" not in entry
    # optional-none fields omitted, present ones kept
    assert entry["port"] == 8888 and entry["transport"] == "streamable-http"


def test_started_at_is_the_canonical_millisecond_z_format():
    """started_at MUST be ISO-8601 UTC, millisecond precision, trailing Z (2026-09-01T
    10:35:34.123Z) — NOT Python's default +00:00 / 6-digit isoformat. This is the format
    that makes registry.json byte-identical across the Dart/TS/PHP/Python kits."""
    s = IronMcpEntry(id="x", namespace="ns", pid=1).to_json()["started_at"]
    assert _CANONICAL_STARTED_AT.match(s), f"non-canonical started_at: {s!r}"
    assert "+00:00" not in s and s.endswith("Z")
    # It is still a real, parseable instant (round-trips through strptime).
    datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ")


def test_from_json_preserves_a_foreign_started_at_verbatim():
    """A timestamp written by another kit is round-tripped byte-for-byte, never reformatted
    — only a MISSING started_at is filled with our canonical value."""
    foreign = "2026-09-01T10:35:34.123Z"
    e = IronMcpEntry.from_json(
        {"id": "x", "namespace": "ns", "pid": 1, "capabilities": {}, "started_at": foreign}
    )
    assert e.started_at == foreign
    missing = IronMcpEntry.from_json({"id": "y", "namespace": "ns", "pid": 1, "capabilities": {}})
    assert _CANONICAL_STARTED_AT.match(missing.started_at)


def test_xdg_path_resolution_matches_dart(monkeypatch, tmp_path):
    """XDG_RUNTIME_DIR wins, then XDG_STATE_HOME, then ~/.local/state — then /ironmcp."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    reg = IronMcpRegistry(is_pid_alive=lambda _p: True)
    reg.register(IronMcpEntry(id="a", namespace="t", pid=1))
    assert os.path.isfile(str(tmp_path / "run" / "ironmcp" / "registry.json"))
