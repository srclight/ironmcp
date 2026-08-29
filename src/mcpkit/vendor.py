"""Emit mcpkit as ONE self-contained file, so every consumer can adopt it today.

WHY THIS EXISTS. The packaging question (publish to PyPI vs vendor vs private-plus-hash-check) is
a decision only Tim can make, and **publishing is irreversible** — a package on PyPI cannot be
un-published in any meaningful sense, and three consumers are public with ~1,900 downloads/month.
Vendoring is reversible.

So the two decisions are separated:

  * ADOPTING the policy   -- reversible, do it now, works for public and private repos identically
  * PUBLISHING a package  -- irreversible, decide later, changes nothing about the policy

A consumer vendors the generated file and imports it. If Tim later chooses to publish, each repo
swaps one import line for a dependency; if he never does, nothing is missing. Either way the estate
runs ONE policy from ONE source today, and no public repo gains a dependency it cannot resolve.

DRIFT IS DETECTABLE, WHICH IS THE WHOLE POINT. The generated file carries the source version, the
upstream git sha and a sha256 of its own body. `verify()` recomputes it, so a hand-edited vendored
copy is caught mechanically -- the failure mode that made plain vendoring unacceptable ("which of
six copies diverged" has no answer) now has one. /healthz already reports mcpkit_version alongside
the server's code_sha, so the answer is also visible from outside at runtime.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

# Dependency order. seams and build import nothing internal; ops needs build; strict needs seams.
_MODULES = ("seams", "build", "ops", "strict")
# Relative imports may be INDENTED (ops.py imports __version__ inside a function), so the pattern
# must allow leading whitespace. Missing that produced a flattened file with a live `from . import`
# inside a function body -- syntactically fine, fatal at call time.
_REL_IMPORT = re.compile(r"^[ \t]*from \.[\w.]* import .*$|^[ \t]*from \. import .*$", re.MULTILINE)
# Every module carries this; Python requires it to appear once, before any other statement.
_FUTURE = re.compile(r"^from __future__ import annotations$\n?", re.MULTILINE)

__all__ = ["render", "verify", "BODY_HASH_MARKER"]

BODY_HASH_MARKER = "# mcpkit-vendored-sha256: "


def _src_dir() -> Path:
    return Path(__file__).resolve().parent


def render(version: str | None = None, code_sha: str | None = None) -> str:
    """Return the single-file form. Deterministic: same inputs, byte-identical output."""
    if version is None:
        from . import __version__ as version  # type: ignore[no-redef]
    if code_sha is None:
        from .build import code_sha as _cs
        code_sha = _cs() or "unknown"

    parts: list[str] = []
    for mod in _MODULES:
        text = (_src_dir() / f"{mod}.py").read_text()
        # Relative imports cannot survive flattening; every name they bind is defined below in
        # dependency order, so dropping the line is correct rather than merely convenient.
        text = _REL_IMPORT.sub("", text)
        text = _FUTURE.sub("", text)
        parts.append(f"# ---- from mcpkit/{mod}.py " + "-" * (58 - len(mod)) + f"\n{text.strip()}\n")

    body = (
        "from __future__ import annotations\n\n"
        f'__version__ = "{version}"\n'
        f'__mcpkit_upstream_sha__ = "{code_sha}"\n\n'
        + "\n".join(parts)
    )
    digest = hashlib.sha256(body.encode()).hexdigest()

    header = f'''"""mcpkit {version} - GENERATED SINGLE-FILE BUILD. DO NOT EDIT.

Regenerate with:  python -m mcpkit.vendor --out <path>
Upstream:         github.com/srclight/mcpkit @ {code_sha}

Hand-editing this file is the failure this package exists to prevent: six copies of one policy,
independently wrong. `mcpkit.vendor.verify()` recomputes the hash below and rejects a modified
copy, so divergence is caught mechanically rather than discovered in a wrong answer.
"""
{BODY_HASH_MARKER}{digest}
'''
    return header + body


def verify(path: str | Path) -> tuple[bool, str]:
    """Check a vendored file has not been hand-edited. Returns (ok, message)."""
    text = Path(path).read_text()
    for line in text.splitlines():
        if line.startswith(BODY_HASH_MARKER):
            claimed = line[len(BODY_HASH_MARKER):].strip()
            break
    else:
        return False, f"{path}: no {BODY_HASH_MARKER.strip()} header — not a generated mcpkit file"
    # The body is everything AFTER the hash line -- the one split point that cannot drift as the
    # header text changes.
    marker_line = BODY_HASH_MARKER + claimed
    body = text.split(marker_line, 1)[1].lstrip("\n")
    actual = hashlib.sha256(body.encode()).hexdigest()
    if actual != claimed:
        return False, (
            f"{path}: MODIFIED. claimed sha256={claimed[:16]}… actual={actual[:16]}…\n"
            "A vendored copy has been hand-edited. Regenerate from upstream instead — the point "
            "of the generated form is that six copies cannot silently diverge."
        )
    return True, f"{path}: matches upstream (sha256={actual[:16]}…)"


def _main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Emit or verify the single-file mcpkit build.")
    ap.add_argument("--out", help="write the generated file here")
    ap.add_argument("--check", help="verify an existing vendored file instead")
    a = ap.parse_args()
    if a.check:
        ok, msg = verify(a.check)
        print(msg)
        raise SystemExit(0 if ok else 1)
    text = render()
    if a.out:
        Path(a.out).write_text(text)
        print(f"wrote {a.out} ({len(text.splitlines())} lines)")
    else:
        print(text, end="")


if __name__ == "__main__":
    _main()
