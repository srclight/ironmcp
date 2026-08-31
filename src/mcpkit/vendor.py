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

# Dependency order. seams and build import nothing internal; ops needs build; strict needs seams;
# conformance imports nothing internal (it operates on any mcp object) so it goes last.
#
# conformance ships INSIDE the hashed policy DELIBERATELY, not as a side effect. A vendored consumer
# imports its guard from this one file and nothing else -- so for it to drop its own hand-written
# "all tools are closed" test (the five that already drifted) and call the shared check instead, the
# check must live here too. The consequence is honest: a change to the conformance CONTRACT registers
# as a policy change under --check, and that is correct -- a consumer whose conformance bar moved
# SHOULD re-vendor to get the new bar. If it ever churns faster than enforcement, split it into a
# second vendored file then; not before.
_MODULES = ("seams", "build", "ops", "strict", "conformance")
# Relative imports may be INDENTED (ops.py imports __version__ inside a function), so the pattern
# must allow leading whitespace. Missing that produced a flattened file with a live `from . import`
# inside a function body -- syntactically fine, fatal at call time.
_REL_IMPORT = re.compile(r"^[ \t]*from \.[\w.]* import .*$|^[ \t]*from \. import .*$", re.MULTILINE)
# Every module carries this; Python requires it to appear once, before any other statement.
_FUTURE = re.compile(r"^from __future__ import annotations$\n?", re.MULTILINE)

__all__ = ["render", "verify", "BODY_HASH_MARKER"]

BODY_HASH_MARKER = "# mcpkit-vendored-sha256: "
POLICY_HASH_MARKER = "# mcpkit-policy-sha256: "
PROVENANCE_SENTINEL = "# ==== mcpkit provenance - nothing below this line is policy code ===="

# The tail is executable Python, so every line must match this whitelist EXACTLY (note the
# anchors - `$` is the load-bearing character). A line that LOOKS like provenance but does not
# match exactly is a hard error, never a silent normalisation: without that, a tamperer formats
# the line so it stops matching and it silently becomes "policy".
_TAIL_EXACT = re.compile(
    r'^(?:__version__ = "[0-9A-Za-z.+!-]{1,32}"'
    r'|__mcpkit_upstream_sha__ = "[0-9a-f]{7,40}(?:\+dirty)?")$'
)


def _src_dir() -> Path:
    return Path(__file__).resolve().parent


def _upstream_sha() -> str | None:
    """The revision of mcpkit's own checkout, independent of where the generator was invoked."""
    import subprocess
    root = _src_dir()
    try:
        out = subprocess.run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5)
        if out.returncode != 0:
            return None
        sha = out.stdout.strip() or None
        if sha:
            dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain"],
                                   capture_output=True, text=True, timeout=5)
            if dirty.returncode == 0 and dirty.stdout.strip():
                sha += "+dirty"
        return sha
    except Exception:
        return None


def render(version: str | None = None, code_sha: str | None = None) -> str:
    """Return the single-file form. Deterministic: same inputs, byte-identical output."""
    if version is None:
        from . import __version__ as version  # type: ignore[no-redef]
    if code_sha is None:
        # MUST resolve from mcpkit's OWN tree, not the cwd. build.code_sha() answers "what revision
        # is this process running from", which is the consumer's repo when the generator is invoked
        # from inside one. Measured 2026-08-29 during the zhcorpus migration: the vendored file
        # claimed "upstream @ e04746d+dirty", which was zhcorpus's HEAD and zhcorpus's 18 dirty
        # files. Every consumer would have stamped a different upstream, making the provenance
        # header actively misleading -- worse than absent.
        code_sha = _upstream_sha() or "unknown"

    parts: list[str] = []
    for mod in _MODULES:
        text = (_src_dir() / f"{mod}.py").read_text()
        # Relative imports cannot survive flattening; every name they bind is defined below in
        # dependency order, so dropping the line is correct rather than merely convenient.
        text = _REL_IMPORT.sub("", text)
        text = _FUTURE.sub("", text)
        parts.append(f"# ---- from mcpkit/{mod}.py " + "-" * (58 - len(mod)) + f"\n{text.strip()}\n")

    # POLICY section: everything a behaviour-change could live in. Hashed separately so
    # "did behaviour change?" has a mechanical answer instead of being punted to a human.
    policy = "from __future__ import annotations\n\n" + "\n".join(parts)
    policy_digest = hashlib.sha256(policy.encode()).hexdigest()

    # PROVENANCE tail: after a fixed sentinel, excluded from the policy hash by TRUNCATION,
    # not by pattern-stripping. A strip-what-matches blacklist was demonstrated exploitable
    # (canes-fideles-d8, 2026-08-29): code appended to a provenance-shaped line was deleted
    # before hashing, so the verifier reassured about a file carrying smuggled module-level
    # Python. Truncation at a marker needs no matching; the tail is then held to a strict
    # whitelist grammar because it is executable Python either way.
    tail = (
        PROVENANCE_SENTINEL + "\n"
        f'__version__ = "{version}"\n'
        f'__mcpkit_upstream_sha__ = "{code_sha}"\n'
    )
    body = policy + "\n" + tail
    digest = hashlib.sha256(body.encode()).hexdigest()

    header = f'''"""mcpkit {version} - GENERATED SINGLE-FILE BUILD. DO NOT EDIT.

Regenerate with:  python -m mcpkit.vendor --out <path>
Upstream:         github.com/srclight/mcpkit @ {code_sha}

Hand-editing this file is the failure this package exists to prevent: six copies of one policy,
independently wrong. `mcpkit.vendor.verify()` recomputes the hash below and rejects a modified
copy, so divergence is caught mechanically rather than discovered in a wrong answer.
"""
{BODY_HASH_MARKER}{digest}
{POLICY_HASH_MARKER}{policy_digest}
'''
    return header + body


def embedded_info(path: str | Path) -> dict[str, str | None]:
    """Read the version and upstream sha a vendored copy claims."""
    import re as _re
    text = Path(path).read_text()
    v = _re.search(r'^__version__ = "([^"]+)"', text, _re.MULTILINE)
    u = _re.search(r'^__mcpkit_upstream_sha__ = "([^"]+)"', text, _re.MULTILINE)
    return {"version": v.group(1) if v else None, "upstream_sha": u.group(1) if u else None}


def _split_policy(body: str, path) -> tuple[str, list[str]]:
    """Split a vendored body into (policy, tail_lines) at the sentinel. Truncation, not
    pattern-stripping: nothing in the policy section needs to be matched, so nothing can be
    disguised to dodge the split."""
    if PROVENANCE_SENTINEL not in body:
        raise ValueError(f"{path}: no provenance sentinel - not a current-format mcpkit file")
    policy, _, tail = body.partition("\n" + PROVENANCE_SENTINEL + "\n")
    # Return the policy EXACTLY as render() hashed it - no normalisation. An earlier draft
    # appended a newline here and rejected every honest copy with a policy-hash mismatch.
    return policy, [l for l in tail.splitlines() if l.strip()]


def verify(path: str | Path, *, check_stale: bool = True) -> tuple[bool, str]:
    """Check a vendored file is unmodified, untampered, and not stale.

    THREE different failures, in order of nastiness:
      * hand-edit anywhere            -> whole-file hash mismatch: MODIFIED
      * tampering in the provenance   -> tail line fails the exact whitelist grammar: TAMPERED.
        Hard error, never a silent normalisation - the demonstrated exploit appended executable
        code to a provenance-shaped line and a stripping verifier vouched for it.
      * staleness                     -> answered by the POLICY hash, mechanically. Provenance-only
        churn (same policy, newer upstream commit) is OK and says so; a policy change is named.
    """
    text = Path(path).read_text()
    claimed = claimed_policy = None
    for line in text.splitlines():
        if line.startswith(BODY_HASH_MARKER):
            claimed = line[len(BODY_HASH_MARKER):].strip()
        elif line.startswith(POLICY_HASH_MARKER):
            claimed_policy = line[len(POLICY_HASH_MARKER):].strip()
    if claimed is None:
        return False, f"{path}: no {BODY_HASH_MARKER.strip()} header - not a generated mcpkit file"

    # Body = everything after the last header marker line.
    last_marker = POLICY_HASH_MARKER + claimed_policy if claimed_policy else BODY_HASH_MARKER + claimed
    body = text.split(last_marker, 1)[1].lstrip("\n")
    actual = hashlib.sha256(body.encode()).hexdigest()
    if actual != claimed:
        return False, (
            f"{path}: MODIFIED. claimed sha256={claimed[:16]}... actual={actual[:16]}...\n"
            "A vendored copy has been hand-edited. Regenerate from upstream instead - the point "
            "of the generated form is that six copies cannot silently diverge."
        )

    try:
        policy, tail_lines = _split_policy(body, path)
    except ValueError as e:
        return False, str(e)
    for i, line in enumerate(tail_lines, 1):
        if not _TAIL_EXACT.match(line):
            return False, (
                f"{path}: TAMPERED provenance, tail line {i} fails the exact grammar: {line[:80]!r}\n"
                "The tail is executable Python; a line that looks like provenance but does not "
                "match exactly is refused, never normalised away."
            )
    actual_policy = hashlib.sha256(policy.encode()).hexdigest()
    if claimed_policy and actual_policy != claimed_policy:
        return False, f"{path}: policy hash mismatch - header claims {claimed_policy[:16]}..., body is {actual_policy[:16]}..."

    info = embedded_info(path)
    if check_stale:
        from . import __version__ as current_version
        if info["version"] != current_version:
            return False, (
                f"{path}: STALE. vendored mcpkit {info['version']}, upstream is {current_version}. "
                f"Regenerate: python -m mcpkit.vendor --out {path}"
            )
        # The mechanical answer to "did that commit change behaviour": compare policy hashes.
        current_policy = _current_policy_hash()
        if current_policy and actual_policy != current_policy:
            return False, (
                f"{path}: POLICY CHANGED upstream. vendored policy {actual_policy[:16]}..., "
                f"current {current_policy[:16]}... Regenerate: python -m mcpkit.vendor --out {path}"
            )
    return True, (f"{path}: OK - mcpkit {info['version']} policy {actual_policy[:16]}... "
                  f"from {info['upstream_sha']}, unmodified")


def _current_policy_hash() -> str | None:
    """Policy hash of what render() would emit right now."""
    try:
        text = render()
        body = text.split(POLICY_HASH_MARKER, 1)[1].split("\n", 1)[1].lstrip("\n")
        policy, _ = _split_policy(body, "<render>")
        return hashlib.sha256(policy.encode()).hexdigest()
    except Exception:
        return None


DEFAULT_MANIFEST = Path(__file__).resolve().parent.parent.parent / "consumers.txt"


def audit(manifest: str | Path = DEFAULT_MANIFEST) -> tuple[bool, list[str]]:
    """Verify every known vendored copy. SILENT ON SUCCESS, loud on change.

    Steady-state noise teaches people to stop reading (the estate's nightwatch was RED for days,
    in front of a human at every session start, and was read past every time - habituation, not
    placement, was the failure). So per-copy output only on a problem; success is one line.
    """
    lines = []
    problems = []
    paths = [l.strip() for l in Path(manifest).read_text().splitlines()
             if l.strip() and not l.strip().startswith("#")]
    for raw in paths:
        pth = Path(raw).expanduser()
        if not pth.exists():
            problems.append(f"MISSING: {pth}")
            continue
        ok, msg = verify(pth)
        if not ok:
            problems.append(msg)
    if problems:
        return False, problems
    return True, [f"audit: {len(paths)}/{len(paths)} vendored copies current and unmodified"]


def _main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Emit or verify the single-file mcpkit build.")
    ap.add_argument("--out", help="write the generated file here")
    ap.add_argument("--check", help="verify an existing vendored file instead")
    ap.add_argument("--audit", action="store_true",
                    help="verify every vendored copy listed in the consumer manifest")
    ap.add_argument("--manifest", help="path to the consumer manifest (default: consumers.txt)")
    a = ap.parse_args()
    if a.audit:
        ok, msgs = audit(a.manifest or DEFAULT_MANIFEST)
        for m in msgs:
            print(m)
        raise SystemExit(0 if ok else 1)
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
