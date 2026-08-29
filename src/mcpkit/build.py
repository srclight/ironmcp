"""Report the code this process is actually running.

WHY. On 2026-08-26 seven stale MCP servers ran simultaneously, each answering from the snapshot of
its source it launched with. From a client's side a stale server is indistinguishable from a current
one: same tool list, same response shape, same confident payload. A server that cannot say which
revision it is cannot be caught.

Stamped ONCE at import and never re-read. A value that changes under a running process is worse than
none -- it would report the checkout's HEAD, not the code in memory, which is exactly the lie being
guarded against. ``None`` is honest and preferable to a guess.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

__all__ = ["code_sha", "started_at", "uptime_s"]

_STARTED_AT = time.time()


def _resolve_sha() -> str | None:
    root = os.environ.get("MCPKIT_CODE_ROOT") or str(Path.cwd())
    try:
        out = subprocess.run(
            ["git", "-C", root, "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode != 0:
            return None
        sha = out.stdout.strip() or None
        if sha:
            dirty = subprocess.run(
                ["git", "-C", root, "status", "--porcelain"],
                capture_output=True, text=True, timeout=5,
            )
            # A dirty tree means the sha does not describe what is running. Say so rather than
            # implying a clean correspondence.
            if dirty.returncode == 0 and dirty.stdout.strip():
                sha += "+dirty"
        return sha
    except Exception:
        return None


_CODE_SHA = _resolve_sha()


def code_sha() -> str | None:
    """The revision stamped at import. None if it could not be determined."""
    return _CODE_SHA


def started_at() -> float:
    return _STARTED_AT


def uptime_s() -> float:
    return time.time() - _STARTED_AT
