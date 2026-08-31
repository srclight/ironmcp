"""The generated single-file build must be equivalent, reproducible, and honestly stamped."""

import subprocess
import sys
from pathlib import Path

from mcpkit.vendor import BODY_HASH_MARKER, render, verify


def test_generation_is_deterministic(tmp_path):
    a, b = render(), render()
    assert a == b, "vendor output must be byte-reproducible or the hash check is meaningless"


def test_hash_header_accepts_an_unmodified_file(tmp_path):
    f = tmp_path / "mcpkit.py"
    f.write_text(render())
    ok, msg = verify(f)
    assert ok, msg


def test_hash_header_rejects_a_hand_edit(tmp_path):
    f = tmp_path / "mcpkit.py"
    f.write_text(render().replace("Nothing was executed", "Nothing happened"))
    ok, msg = verify(f)
    assert not ok
    assert "MODIFIED" in msg


def test_upstream_sha_is_MCPKITS_not_the_callers(tmp_path, monkeypatch):
    """Provenance must not depend on where the generator was run.

    Found in the zhcorpus migration: invoked from a consumer repo, the header stamped that repo's
    HEAD and dirty flag as "upstream mcpkit". Every consumer would have claimed a different
    upstream -- a misleading provenance header is worse than none.
    """
    monkeypatch.chdir(tmp_path)                     # cwd is now NOT an mcpkit checkout
    monkeypatch.setenv("MCPKIT_CODE_ROOT", str(tmp_path))
    text = render()
    real = subprocess.run(
        ["git", "-C", str(Path(__file__).resolve().parent.parent), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True).stdout.strip()
    assert real and real in text, "header must carry mcpkit's own revision"


def test_generated_file_is_importable_and_self_contained(tmp_path):
    f = tmp_path / "mcpkit_gen.py"
    f.write_text(render())
    r = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, %r); import mcpkit_gen as m; "
         "assert m.StrictArgsMCP and m.attach_healthz and m.code_sha; print('ok')" % str(tmp_path)],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_a_stale_copy_is_rejected_even_though_its_hash_is_valid(tmp_path):
    """The hash catches hand-edits; it says nothing about AGE.

    Without this, four vendored copies three versions apart all pass verification, and vendoring is
    strictly worse than a pinned dependency — which at least records a version.
    (canes-fideles-d8's verification, 2026-08-29.)
    """
    f = tmp_path / "mcpkit.py"
    f.write_text(render(version="0.0.9"))     # correctly generated, correctly hashed, OLD
    ok, msg = verify(f)
    assert not ok, "a stale vendored copy must not pass verification"
    assert "STALE" in msg
    assert "0.0.9" in msg                      # says what it has
    assert "regenerate" in msg.lower()         # says what to do


def test_staleness_check_can_be_disabled_for_hash_only_use(tmp_path):
    f = tmp_path / "mcpkit.py"
    f.write_text(render(version="0.0.9"))
    ok, _ = verify(f, check_stale=False)
    assert ok, "hash-only verification must still pass on an unmodified older copy"


# ---- adversarial battery from the pack's Q1 attack (2026-08-29) --------------------------------

import hashlib as _hl
import re as _re

from mcpkit.vendor import BODY_HASH_MARKER, audit


def _rehash(t: str) -> str:
    """What a competent tamperer does: recompute the self-describing whole-file hash."""
    claimed = _re.search(_re.escape(BODY_HASH_MARKER) + r"([0-9a-f]{64})", t).group(1)
    body = t.split("# mcpkit-policy-sha256: ", 1)[1].split("\n", 1)[1].lstrip("\n")
    return t.replace(claimed, _hl.sha256(body.encode()).hexdigest())


def test_smuggled_code_on_a_provenance_line_is_refused_even_with_a_fixed_hash(tmp_path):
    """The demonstrated exploit: append executable Python to a provenance-shaped line, then
    recompute the whole-file hash. A stripping (blacklist) verifier deleted the whole line before
    hashing and VOUCHED for the file. The sentinel design refuses at the tail grammar instead —
    and the refusal must not depend on the tamperer forgetting to fix the hash."""
    evil = _re.sub(r'(__mcpkit_upstream_sha__ = "[0-9a-f]+(?:\+dirty)?")',
                   r'\1; import os; SKIP = os.environ.get("SKIP_GUARD")', render(), count=1)
    f = tmp_path / "m.py"
    f.write_text(_rehash(evil))
    ok, msg = verify(f)
    assert not ok
    assert "TAMPERED" in msg, f"must refuse via the grammar, not by luck: {msg[:120]}"


def test_a_looks_but_not_exact_provenance_line_is_refused_not_normalised(tmp_path):
    """Without the LOOKS-but-not-EXACT hard error, a tamperer reformats the line so it stops
    matching and it silently becomes policy — the hash still catches drift, but nobody learns the
    file was touched in a provenance slot. Two spaces instead of one is enough to test the anchor."""
    reform = _re.sub(r'__mcpkit_upstream_sha__ = ("[0-9a-f]+(?:\+dirty)?")',
                     r'__mcpkit_upstream_sha__  = \1', render(), count=1)
    f = tmp_path / "m.py"
    f.write_text(_rehash(reform))
    ok, msg = verify(f)
    assert not ok and "TAMPERED" in msg


def test_provenance_only_rotation_is_OK_and_says_policy_identical(tmp_path):
    """The wart this design exists to fix: an upstream commit that changes nothing behavioural
    must NOT produce 'regenerate if that commit changed behaviour' — the machine now answers."""
    f = tmp_path / "m.py"
    f.write_text(render(code_sha="0000000"))
    ok, msg = verify(f)
    assert ok, msg
    assert "policy" in msg.lower()


def test_audit_is_silent_on_success_and_loud_on_a_missing_copy(tmp_path):
    good = tmp_path / "a.py"
    good.write_text(render())
    manifest = tmp_path / "consumers.txt"
    manifest.write_text(f"{good}\n")
    ok, msgs = audit(manifest)
    assert ok and len(msgs) == 1 and "1/1" in msgs[0]

    manifest.write_text(f"{good}\n{tmp_path}/ghost.py\n")
    ok, msgs = audit(manifest)
    assert not ok
    assert any("MISSING" in m for m in msgs)


def test_crlf_checkout_does_not_read_as_TAMPERED(tmp_path):
    """git autocrlf on a Windows clone rewrites LF->CRLF. verify() must not flag that as tampering
    — a false TAMPERED is the worst direction for a security check, because the first response to a
    false alarm is to stop trusting the alarm. (Predicted by canes-fideles-d8; survives because
    Path.read_text() does universal-newline translation — pinned here so it stays deliberate.)"""
    f = tmp_path / "m.py"
    f.write_bytes(render().replace("\n", "\r\n").encode())
    ok, msg = verify(f)
    assert ok, f"CRLF checkout falsely flagged: {msg}"
