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
    expect(j.overall_status).toBe("ready");
    expect((j.libs as Record<string, unknown>[])[0].symbols_ok).toBe(3);
    expect((j.features as Record<string, unknown>[])[0].requires).toEqual(["x"]);
    expect((j.data_files as Record<string, unknown>[])[0].found).toBe(true);
  });

  it("a lib with no symbol counts still serialises symbols_checked/ok as 0", () => {
    const j = new ReadinessReport({
      appVersion: "1",
      libs: [{ name: "x", loaded: false }],
    }).toJSON();
    const lib = (j.libs as Record<string, unknown>[])[0];
    expect(lib.symbols_checked).toBe(0);
    expect(lib.symbols_ok).toBe(0);
  });
});
