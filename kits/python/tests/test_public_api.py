"""The v2 public API surface is importable and complete."""


def test_v2_public_api_imports():
    from ironmcp import (  # noqa: F401
        Result,
        StrictArgsMiddleware,
        aassert_enforces_v2,
        assert_enforces_v2,
        code_sha,
        health_payload,
        make_bearer_asgi,
        run_corpus,
        strict_server,
    )


def test_v2_names_reachable_from_top_level_lazily():
    import ironmcp

    for name in ("StrictArgsMiddleware", "strict_server", "aassert_enforces_v2",
                 "run_corpus", "health_payload", "make_bearer_asgi"):
        assert getattr(ironmcp, name) is not None


def test_spec_and_corpus_present():
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[3]
    assert (root / "spec" / "strict-args.md").is_file()
    assert (root / "spec" / "conformance.md").is_file()
    assert list((root / "conformance" / "cases").glob("*.json"))
