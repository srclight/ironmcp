import { describe, it, expect } from "vitest";
import { ReadinessReport, type FeatureReadiness } from "../src/readiness.js";

const report = (features: FeatureReadiness[]) => new ReadinessReport({ appVersion: "1", features });

describe("ReadinessReport", () => {
  it("overall EXCLUDES blocked and off from the verdict (invariant #7)", () => {
    const r = report([
      { id: "a", label: "A", status: "ready" },
      { id: "b", label: "B", status: "blocked" },
      { id: "c", label: "C", status: "off" },
    ]);
    expect(r.overallStatus).toBe("ready");
  });

  it("all blocked/off still yields ready (the dev-box case), not failed", () => {
    const r = report([
      { id: "a", label: "A", status: "blocked" },
      { id: "b", label: "B", status: "off" },
    ]);
    expect(r.overallStatus).toBe("ready");
  });

  it("a failed counted feature makes overall failed", () => {
    expect(
      report([
        { id: "a", label: "A", status: "ready" },
        { id: "b", label: "B", status: "failed" },
      ]).overallStatus,
    ).toBe("failed");
  });

  it("a degraded feature (no failures) makes overall degraded", () => {
    expect(report([{ id: "a", label: "A", status: "degraded" }]).overallStatus).toBe("degraded");
  });

  it("NO counted features (empty, or all blocked/off) yields ready — zero features is not a failure", () => {
    expect(report([]).overallStatus).toBe("ready");
    expect(new ReadinessReport({ appVersion: "1" }).overallStatus).toBe("ready"); // features omitted
  });

  it("failed takes precedence over degraded when BOTH are present among counted features", () => {
    // Directly pin the precedence: a report holding a failed AND a degraded counted feature is
    // 'failed', never 'degraded'. (The other failed-test pairs ready+failed only.)
    expect(
      report([
        { id: "a", label: "A", status: "degraded" },
        { id: "b", label: "B", status: "failed" },
        { id: "c", label: "C", status: "ready" },
      ]).overallStatus,
    ).toBe("failed");
    // order-independent: degraded listed AFTER failed still resolves to failed
    expect(
      report([
        { id: "a", label: "A", status: "failed" },
        { id: "b", label: "B", status: "degraded" },
      ]).overallStatus,
    ).toBe("failed");
  });

  it("toJSON is stable snake_case with the computed verdict", () => {
    const j = new ReadinessReport({
      appVersion: "2.0",
      nativeVersion: "1.5",
      features: [{ id: "a", label: "A", status: "ready", requires: ["x"] }],
      libs: [{ name: "libfoo", loaded: true, symbolsChecked: 3, symbolsOk: 3 }],
      dataFiles: [{ label: "dict", found: true, path: "/x" }],
      platform: { os: "linux" },
    }).toJSON();
    expect(j.app_version).toBe("2.0");
    expect(j.native_version).toBe("1.5");
    expect(j.status).toBe("ready"); // was overall_status
    expect(j).not.toHaveProperty("libs"); // renamed to `dependencies`
    // features / dependencies / data_files are objects keyed by id/name.
    const feats = j.features as Record<string, Record<string, unknown>>;
    const deps = j.dependencies as Record<string, Record<string, unknown>>;
    const files = j.data_files as Record<string, Record<string, unknown>>;
    expect(feats.a.requires).toEqual(["x"]);
    expect(feats.a).not.toHaveProperty("id"); // id is the key
    expect(deps.libfoo.symbols_ok).toBe(3);
    expect(files.dict.found).toBe(true);
    expect(files.dict).not.toHaveProperty("label");
  });

  it("omits absent optional fields: an empty/absent requires, and a data file with no path", () => {
    // The OMISSION branches: featureToJson drops `requires` when empty or absent, and
    // dataFileToJson drops `path` when absent — the false-branch of each `!= null`/length guard.
    const j = new ReadinessReport({
      appVersion: "1",
      features: [
        { id: "a", label: "A", status: "ready" }, // requires absent
        { id: "b", label: "B", status: "ready", requires: [] }, // requires present but empty
      ],
      dataFiles: [{ label: "dict", found: false }], // path absent
    }).toJSON();
    const feats = j.features as Record<string, Record<string, unknown>>;
    expect(feats.a).not.toHaveProperty("requires");
    expect(feats.b).not.toHaveProperty("requires"); // empty array is dropped, not emitted as []
    expect(feats.a).not.toHaveProperty("details");
    expect(feats.a).not.toHaveProperty("reason");
    const files = j.data_files as Record<string, Record<string, unknown>>;
    expect(files.dict).not.toHaveProperty("path");
    expect(files.dict.found).toBe(false);
  });

  it("a dependency with no symbol probe omits the FFI symbol counts (services/dbs stay clean)", () => {
    const j = new ReadinessReport({
      appVersion: "1",
      libs: [{ name: "postgres", loaded: true }],
    }).toJSON();
    const dep = (j.dependencies as Record<string, Record<string, unknown>>).postgres;
    expect(dep.loaded).toBe(true);
    expect(dep).not.toHaveProperty("symbols_checked");
    expect(dep).not.toHaveProperty("symbols_ok");
  });
});
