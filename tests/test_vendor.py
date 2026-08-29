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
