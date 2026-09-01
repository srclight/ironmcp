// Feature readiness. `blocked` (the environment cannot satisfy it) and `off` (intentionally
// disabled) are EXCLUDED from the overall verdict — a dev box that can never meet the environment
// still reports `ready` (loqu8 invariant #7). ironmcp owns the SHAPE + the verdict semantics;
// the app supplies the feature/lib/data checks (no dart:ffi / node native dep here). Pure.

export type ReadinessStatus = "ready" | "degraded" | "failed" | "blocked" | "off";

export type FeatureReadiness = {
  id: string;
  label: string;
  status: ReadinessStatus;
  requires?: string[];
  details?: string;
  reason?: string;
};

export type LibraryStatus = {
  name: string;
  loaded: boolean;
  symbolsChecked?: number;
  symbolsOk?: number;
  error?: string;
};

export type DataFileStatus = {
  label: string;
  found: boolean;
  path?: string;
};

export type ReadinessReportInput = {
  appVersion: string;
  nativeVersion?: string;
  features?: FeatureReadiness[];
  libs?: LibraryStatus[];
  dataFiles?: DataFileStatus[];
  platform?: Record<string, unknown>;
};

function featureToJson(f: FeatureReadiness): Record<string, unknown> {
  const j: Record<string, unknown> = { id: f.id, label: f.label, status: f.status };
  if (f.requires && f.requires.length > 0) j.requires = f.requires;
  if (f.details != null) j.details = f.details;
  if (f.reason != null) j.reason = f.reason;
  return j;
}

function libToJson(l: LibraryStatus): Record<string, unknown> {
  const j: Record<string, unknown> = {
    name: l.name,
    loaded: l.loaded,
    symbols_checked: l.symbolsChecked ?? 0,
    symbols_ok: l.symbolsOk ?? 0,
  };
  if (l.error != null) j.error = l.error;
  return j;
}

function dataFileToJson(d: DataFileStatus): Record<string, unknown> {
  const j: Record<string, unknown> = { label: d.label, found: d.found };
  if (d.path != null) j.path = d.path;
  return j;
}

/** A full readiness report. */
export class ReadinessReport {
  readonly appVersion: string;
  readonly nativeVersion?: string;
  readonly features: FeatureReadiness[];
  readonly libs: LibraryStatus[];
  readonly dataFiles: DataFileStatus[];
  readonly platform: Record<string, unknown>;

  constructor(input: ReadinessReportInput) {
    this.appVersion = input.appVersion;
    this.nativeVersion = input.nativeVersion;
    this.features = input.features ?? [];
    this.libs = input.libs ?? [];
    this.dataFiles = input.dataFiles ?? [];
    this.platform = input.platform ?? {};
  }

  /** Overall verdict from the features that COUNT — `blocked`/`off` are excluded (invariant #7).
   *  failed > degraded > ready. */
  get overallStatus(): ReadinessStatus {
    const counted = this.features.filter((f) => f.status !== "blocked" && f.status !== "off");
    if (counted.some((f) => f.status === "failed")) return "failed";
    if (counted.some((f) => f.status === "degraded")) return "degraded";
    return "ready";
  }

  toJSON(): Record<string, unknown> {
    const j: Record<string, unknown> = { app_version: this.appVersion };
    if (this.nativeVersion != null) j.native_version = this.nativeVersion;
    j.overall_status = this.overallStatus;
    j.features = this.features.map(featureToJson);
    j.libs = this.libs.map(libToJson);
    j.data_files = this.dataFiles.map(dataFileToJson);
    j.platform = this.platform;
    return j;
  }
}
