"""F6 readiness: the overall verdict EXCLUDES blocked and off (#7)."""

from ironmcp import (
    DataFileStatus,
    FeatureReadiness,
    LibraryStatus,
    ReadinessReport,
    ReadinessStatus,
)


def _report(features):
    return ReadinessReport(app_version="1", features=features)


def test_overall_excludes_blocked_and_off_from_the_verdict_invariant_7():
    r = _report(
        [
            FeatureReadiness(id="a", label="A", status=ReadinessStatus.ready),
            FeatureReadiness(id="b", label="B", status=ReadinessStatus.blocked),
            FeatureReadiness(id="c", label="C", status=ReadinessStatus.off),
        ]
    )
    assert r.overall_status == ReadinessStatus.ready


def test_all_blocked_off_still_yields_ready_the_dev_box_case_not_failed():
    r = _report(
        [
            FeatureReadiness(id="a", label="A", status=ReadinessStatus.blocked),
            FeatureReadiness(id="b", label="B", status=ReadinessStatus.off),
        ]
    )
    assert r.overall_status == ReadinessStatus.ready


def test_a_failed_counted_feature_makes_overall_failed():
    r = _report(
        [
            FeatureReadiness(id="a", label="A", status=ReadinessStatus.ready),
            FeatureReadiness(id="b", label="B", status=ReadinessStatus.failed),
        ]
    )
    assert r.overall_status == ReadinessStatus.failed


def test_a_degraded_feature_no_failures_makes_overall_degraded():
    r = _report(
        [FeatureReadiness(id="a", label="A", status=ReadinessStatus.degraded)]
    )
    assert r.overall_status == ReadinessStatus.degraded


def test_a_blocked_feature_never_masks_a_failed_one():
    """A blocked feature alongside a failed one: the failed one still decides."""
    r = _report(
        [
            FeatureReadiness(id="a", label="A", status=ReadinessStatus.blocked),
            FeatureReadiness(id="b", label="B", status=ReadinessStatus.failed),
        ]
    )
    assert r.overall_status == ReadinessStatus.failed


def test_to_json_is_stable_snake_case_with_the_computed_verdict():
    j = ReadinessReport(
        app_version="2.0",
        native_version="1.5",
        features=[
            FeatureReadiness(
                id="a", label="A", status=ReadinessStatus.ready, requires=["x"]
            )
        ],
        libs=[
            LibraryStatus(name="libfoo", loaded=True, symbols_checked=3, symbols_ok=3)
        ],
        data_files=[DataFileStatus(label="dict", found=True, path="/x")],
        platform={"os": "linux"},
    ).to_json()
    assert j["app_version"] == "2.0"
    assert j["overall_status"] == "ready"
    assert j["libs"][0]["symbols_ok"] == 3
    assert j["features"][0]["requires"] == ["x"]
    assert j["data_files"][0]["found"] is True
    assert j["native_version"] == "1.5"


def test_empty_features_list_yields_ready():
    """No features to count is the vacuous-ready edge: overall_status is ready, not failed."""
    assert _report([]).overall_status == ReadinessStatus.ready


def test_degraded_and_failed_together_failed_wins():
    r = _report(
        [
            FeatureReadiness(id="a", label="A", status=ReadinessStatus.degraded),
            FeatureReadiness(id="b", label="B", status=ReadinessStatus.failed),
        ]
    )
    assert r.overall_status == ReadinessStatus.failed


def test_to_json_omits_optional_none_fields():
    """The optional-field omission branches: details/reason/requires (feature), error (lib),
    path (data file) are DROPPED from the JSON when unset — not emitted as null."""
    feat = FeatureReadiness(id="a", label="A", status=ReadinessStatus.ready).to_json()
    assert "details" not in feat and "reason" not in feat and "requires" not in feat

    lib = LibraryStatus(name="libfoo", loaded=True).to_json()
    assert "error" not in lib

    data = DataFileStatus(label="dict", found=False).to_json()
    assert "path" not in data


def test_to_json_emits_optional_fields_when_present():
    """The EMIT branches (the normal degraded/failed path): details/reason (feature) and
    error (lib) are carried through to the JSON verbatim when populated."""
    feat = FeatureReadiness(
        id="a",
        label="A",
        status=ReadinessStatus.degraded,
        details="native lib missing",
        reason="libfoo.so not found on the load path",
    ).to_json()
    assert feat["details"] == "native lib missing"
    assert feat["reason"] == "libfoo.so not found on the load path"

    lib = LibraryStatus(name="libfoo", loaded=False, error="dlopen failed").to_json()
    assert lib["error"] == "dlopen failed"
