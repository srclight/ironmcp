"""Agent-interrogable liveness. An agent reads this to learn WHAT a server is and
WHETHER it is current, without asking a human (the AI-first "self-describing at runtime"
requirement). ``code_sha`` never raises -- an unknown sha reports ``"unknown"``, never a
crash and never a stale value dressed as current."""

from __future__ import annotations

import subprocess
from importlib.metadata import PackageNotFoundError, version

__all__ = ["code_sha", "health_payload"]


def code_sha() -> str:
    """Short git sha of the running tree, or ``"unknown"``. Never raises."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return out or "unknown"
    except Exception:
        return "unknown"


def _mcp_version() -> str:
    try:
        return version("mcp")
    except PackageNotFoundError:
        return "unknown"


def health_payload(name: str, server_version: str) -> dict:
    """A minimal, honest liveness payload for a /healthz route or a health tool."""
    return {
        "status": "ok",
        "name": name,
        "version": server_version,
        "code_sha": code_sha(),
        "mcp_sdk": _mcp_version(),
    }
