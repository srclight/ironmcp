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
