"""Self-discovery of ironmcp servers over a shared, language-neutral registry file.

A Dart iCE, a Python ``*light`` server, and a Node scarlight all read and write the SAME
discovery fabric. The on-disk format is byte-for-byte compatible with
``kits/dart/lib/src/registry.dart`` (READ it): a JSON object keyed by entry-id, each value
an entry of snake_case fields, an ``O_EXCL`` lockfile around every read-modify-write, and
pid-liveness pruning on read.

Entry deliberately carries NO hand-kept tool list — a consumer enumerates a server's tools
via ``tools/list`` on its port (loqu8 invariant #3: the list that drifted from 6 to 66).
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

__all__ = ["IronMcpEntry", "IronMcpRegistry"]


def _now_iso() -> str:
    """ISO-8601 in UTC, matching Dart's ``DateTime.now().toUtc().toIso8601String()``."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class IronMcpEntry:
    """A live ironmcp server's registration. Language-neutral JSON (snake_case)."""

    id: str
    namespace: str
    pid: int
    host: Optional[str] = None
    port: Optional[int] = None
    transport: Optional[str] = None
    version: Optional[str] = None
    code_sha: Optional[str] = None
    capabilities: dict = field(default_factory=dict)
    started_at: str = field(default_factory=_now_iso)

    def to_json(self) -> dict:
        # Key order + optional-field omission mirror the Dart toJson exactly.
        out: dict = {"id": self.id, "namespace": self.namespace, "pid": self.pid}
        if self.host is not None:
            out["host"] = self.host
        if self.port is not None:
            out["port"] = self.port
        if self.transport is not None:
            out["transport"] = self.transport
        if self.version is not None:
            out["version"] = self.version
        if self.code_sha is not None:
            out["code_sha"] = self.code_sha
        out["capabilities"] = self.capabilities
        out["started_at"] = self.started_at
        return out

    @staticmethod
    def from_json(j: dict) -> "IronMcpEntry":
        return IronMcpEntry(
            id=j["id"],
            namespace=j["namespace"],
            pid=int(j["pid"]),
            host=j.get("host"),
            port=j.get("port"),
            transport=j.get("transport"),
            version=j.get("version"),
            code_sha=j.get("code_sha"),
            capabilities=dict(j.get("capabilities") or {}),
            started_at=j.get("started_at") or _now_iso(),
        )


def _default_dir() -> str:
    """XDG_RUNTIME_DIR else XDG_STATE_HOME else ~/.local/state, then ``/ironmcp``.

    Identical to the Dart ``_defaultDir`` so both kits resolve the same file.
    """
    env = os.environ
    base = (
        env.get("XDG_RUNTIME_DIR")
        or env.get("XDG_STATE_HOME")
        or os.path.join(env.get("HOME", "."), ".local", "state")
    )
    return os.path.join(base, "ironmcp")


def _pid_alive_default(pid: int) -> bool:
    """True iff ``pid`` is a live process. Fails OPEN — never prune what we can't verify."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists but owned by another user
    except OSError:
        return True  # fail open


class IronMcpRegistry:
    """File-backed registry with a cross-process O_EXCL lock, pid pruning, and an XDG path."""

    def __init__(
        self,
        *,
        dir: Optional[str] = None,
        is_pid_alive: Optional[Callable[[int], bool]] = None,
        lock_timeout: float = 3.0,
        stale_lock_after: float = 30.0,
    ) -> None:
        self._dir = dir if dir is not None else _default_dir()
        self._is_pid_alive = is_pid_alive or _pid_alive_default
        self.lock_timeout = lock_timeout
        self.stale_lock_after = stale_lock_after

    @property
    def _file(self) -> str:
        return os.path.join(self._dir, "registry.json")

    @property
    def _lock_file(self) -> str:
        return os.path.join(self._dir, "registry.json.lock")

    def register(self, entry: IronMcpEntry) -> None:
        def body() -> None:
            data = self._read()
            data[entry.id] = entry.to_json()
            self._write(data)

        self._with_lock(body)

    def unregister(self, id: str) -> None:
        def body() -> None:
            data = self._read()
            data.pop(id, None)
            self._write(data)

        self._with_lock(body)

    def discover(self) -> list[IronMcpEntry]:
        """Live servers, pruning any whose pid is dead (and rewriting the file if it
        pruned). A hard-killed process is cleaned up lazily on the next reader's scan,
        since its own ``unregister`` never ran (invariant #10)."""
        live: list[IronMcpEntry] = []

        def body() -> None:
            data = self._read()
            pruned = False
            for key in list(data.keys()):
                entry = IronMcpEntry.from_json(dict(data[key]))
                if self._is_pid_alive(entry.pid):
                    live.append(entry)
                else:
                    del data[key]
                    pruned = True
            if pruned:
                self._write(data)

        self._with_lock(body)
        return live

    # --- internals -------------------------------------------------------------

    def _read(self) -> dict:
        try:
            if not os.path.exists(self._file):
                return {}
            with open(self._file, encoding="utf-8") as f:
                txt = f.read()
            if not txt.strip():
                return {}
            return dict(json.loads(txt))
        except Exception:
            return {}  # corrupt/unreadable: start fresh rather than crash

    def _write(self, data: dict) -> None:
        os.makedirs(self._dir, exist_ok=True)
        tmp = f"{self._file}.tmp.{os.getpid()}.{time.time_ns()}"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, self._file)  # atomic on the same filesystem

    def _with_lock(self, body: Callable[[], None]) -> None:
        os.makedirs(self._dir, exist_ok=True)
        deadline = time.monotonic() + self.lock_timeout
        acquired = False
        while True:
            try:
                # O_EXCL: atomic create-or-fail, the cross-process mutex (matches Dart's
                # File.create(exclusive: true)).
                fd = os.open(self._lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(fd)
                acquired = True
                break
            except FileExistsError:
                # A crashed holder can leave a stale lock — steal it past stale_lock_after.
                try:
                    age = time.time() - os.path.getmtime(self._lock_file)
                    if age > self.stale_lock_after:
                        os.unlink(self._lock_file)
                        continue
                except OSError:
                    pass
                if time.monotonic() > deadline:
                    break  # proceed best-effort
                time.sleep(0.005)
        try:
            body()
        finally:
            if acquired:
                try:
                    os.unlink(self._lock_file)
                except OSError:
                    pass
