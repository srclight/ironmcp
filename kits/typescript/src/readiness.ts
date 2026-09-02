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

// `id` is the map key under `features`; `label` is a display hint kept out of the
// wire shape so the per-feature value is byte-identical across kits.
function featureToJson(f: FeatureReadiness): Record<string, unknown> {
  const j: Record<string, unknown> = { status: f.status };
  if (f.requires && f.requires.length > 0) j.requires = f.requires;
  if (f.details != null) j.details = f.details;
  if (f.reason != null) j.reason = f.reason;
  return j;
}

// `name` is the map key under `dependencies`. Symbol counts are FFI-specific, so
// they appear ONLY when a probe ran — a non-native dependency (a service, a
// database) carries just `loaded` and an optional `error`.
function libToJson(l: LibraryStatus): Record<string, unknown> {
  const j: Record<string, unknown> = { loaded: l.loaded };
  const checked = l.symbolsChecked ?? 0;
  if (checked > 0) {
    j.symbols_checked = checked;
    j.symbols_ok = l.symbolsOk ?? 0;
  }
  if (l.error != null) j.error = l.error;
  return j;
}

// `label` is the map key under `data_files`.
function dataFileToJson(d: DataFileStatus): Record<string, unknown> {
  const j: Record<string, unknown> = { found: d.found };
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

  // Ecosystem health-check vocabulary (`status`) + loqu8's map-by-id structure:
  // features/dependencies/data_files are OBJECTS keyed by id/name, so an agent
  // reads `features["<id>"].status` in one hop, there is no list order to keep
  // byte-identical across kits, and duplicate ids cannot hide. `dependencies`
  // (not `libs`) so a server with services rather than native libraries is not
  // misdescribed.
  toJSON(): Record<string, unknown> {
    const j: Record<string, unknown> = { app_version: this.appVersion };
    if (this.nativeVersion != null) j.native_version = this.nativeVersion;
    j.status = this.overallStatus;
    j.features = Object.fromEntries(this.features.map((f) => [f.id, featureToJson(f)]));
    j.dependencies = Object.fromEntries(this.libs.map((l) => [l.name, libToJson(l)]));
    j.data_files = Object.fromEntries(this.dataFiles.map((d) => [d.label, dataFileToJson(d)]));
    j.platform = this.platform;
    return j;
  }
}
