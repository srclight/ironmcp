"""F5 registry: concurrent register loses nothing (#9), dead-pid prune (#10), NO tool
list (#3), and the on-disk format byte-compatible with the Dart kit."""

import json
import os
import re
import time
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


# --- crash-recovery lock branches (the two the cross-process mutex exists for) ----------


def test_stale_lock_is_stolen_past_stale_lock_after(reg_dir):
    """A crashed holder leaves the O_EXCL lockfile behind. A later writer whose age >
    stale_lock_after STEALS it (unlink + continue) rather than blocking forever."""
    os.makedirs(reg_dir, exist_ok=True)
    lock = os.path.join(reg_dir, "registry.json.lock")
    open(lock, "w").close()
    old = time.time() - 3600  # an hour stale
    os.utime(lock, (old, old))
    reg = IronMcpRegistry(
        dir=reg_dir, is_pid_alive=lambda _p: True, stale_lock_after=1.0, lock_timeout=0.05
    )
    reg.register(IronMcpEntry(id="a", namespace="t", pid=1))  # must not hang
    # the stolen lock was acquired for real, so the body ran AND released it
    assert {e.id for e in reg.discover()} == {"a"}
    assert not os.path.exists(lock)


def test_lock_timeout_falls_through_best_effort(reg_dir):
    """A FRESH lock we may not steal + an exceeded deadline -> proceed best-effort WITHOUT
    the lock (the deadlock-avoidance fallthrough). The body still runs; the foreign lock is
    left in place (we never acquired it, so we never unlink it)."""
    os.makedirs(reg_dir, exist_ok=True)
    lock = os.path.join(reg_dir, "registry.json.lock")
    open(lock, "w").close()  # fresh mtime: not stealable under a huge stale_lock_after
    reg = IronMcpRegistry(
        dir=reg_dir, is_pid_alive=lambda _p: True, stale_lock_after=1e9, lock_timeout=0.0
    )
    reg.register(IronMcpEntry(id="a", namespace="t", pid=1))  # proceeds best-effort
    assert {e.id for e in reg.discover()} == {"a"}  # body ran despite no lock
    assert os.path.exists(lock)  # foreign lock left untouched (never acquired)


# --- corrupt / empty registry.json: start fresh, never crash (invariant + fix #5) -------


def test_discover_on_corrupt_json_starts_fresh_not_crash(reg_dir):
    os.makedirs(reg_dir, exist_ok=True)
    with open(os.path.join(reg_dir, "registry.json"), "w") as f:
        f.write("{not valid json at all ]]]")
    reg = IronMcpRegistry(dir=reg_dir, is_pid_alive=lambda _p: True)
    assert reg.discover() == []  # no raise


def test_register_over_corrupt_json_starts_fresh(reg_dir):
    os.makedirs(reg_dir, exist_ok=True)
    with open(os.path.join(reg_dir, "registry.json"), "w") as f:
        f.write("\x00\x01 garbage")
    reg = IronMcpRegistry(dir=reg_dir, is_pid_alive=lambda _p: True)
    reg.register(IronMcpEntry(id="a", namespace="t", pid=1))  # no raise; overwrites garbage
    assert {e.id for e in reg.discover()} == {"a"}


def test_whitespace_only_registry_is_empty(reg_dir):
    os.makedirs(reg_dir, exist_ok=True)
    with open(os.path.join(reg_dir, "registry.json"), "w") as f:
        f.write("   \n\t  ")
    reg = IronMcpRegistry(dir=reg_dir, is_pid_alive=lambda _p: True)
    assert reg.discover() == []


# --- discover() prune is PERSISTED to disk, not merely pruned in memory (fix #3) --------


def test_discover_prune_is_persisted_a_fresh_reader_sees_it_gone(reg_dir):
    """After discover() prunes a dead-pid entry it MUST rewrite the file. Prove persistence
    (not an in-memory re-prune): a FRESH registry that believes EVERY pid is alive must still
    not see the pruned entry — it is gone from disk."""
    writer = IronMcpRegistry(dir=reg_dir, is_pid_alive=lambda pid: pid != 2)
    writer.register(IronMcpEntry(id="a", namespace="t", pid=1))
    writer.register(IronMcpEntry(id="b", namespace="t", pid=2))  # dead pid
    assert {e.id for e in writer.discover()} == {"a"}  # prunes b, rewrites the file
    reader = IronMcpRegistry(dir=reg_dir, is_pid_alive=lambda _p: True)  # trusts every pid
    assert {e.id for e in reader.discover()} == {"a"}  # b was written out of the file, not just skipped


# --- the REAL default pid-liveness probe (every other test injects a fake) --------------


def test_pid_alive_default_fails_open_and_closed_correctly(monkeypatch):
    from ironmcp.registry import _pid_alive_default

    assert _pid_alive_default(0) is False       # pid <= 0
    assert _pid_alive_default(-1) is False
    assert _pid_alive_default(os.getpid()) is True  # this very process is alive

    # a reliably-dead pid: spawn a child, reap it, then probe -> ProcessLookupError -> False
    import subprocess

    p = subprocess.Popen(["true"])
    p.wait()
    assert _pid_alive_default(p.pid) is False

    # PermissionError -> True (exists, owned by another user); OSError -> True (fail OPEN)
    def _perm(_pid, _sig):
        raise PermissionError

    def _oserr(_pid, _sig):
        raise OSError

    monkeypatch.setattr(os, "kill", _perm)
    assert _pid_alive_default(99999) is True
    monkeypatch.setattr(os, "kill", _oserr)
    assert _pid_alive_default(99999) is True


# --- the two lower rungs of the _default_dir precedence chain ---------------------------


def test_default_dir_falls_back_to_xdg_state_home(monkeypatch):
    from ironmcp.registry import _default_dir

    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    monkeypatch.setenv("XDG_STATE_HOME", "/xdg/state")
    assert _default_dir() == os.path.join("/xdg/state", "ironmcp")


def test_default_dir_final_fallback_is_local_state(monkeypatch):
    from ironmcp.registry import _default_dir

    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.setenv("HOME", "/home/tester")
    assert _default_dir() == os.path.join("/home/tester", ".local", "state", "ironmcp")
