/// Feature readiness. `blocked` (the environment cannot satisfy it) and `off`
/// (intentionally disabled) are EXCLUDED from the overall verdict — a dev box
/// that can never meet the environment still reports `ready` (loqu8 invariant #7).
enum ReadinessStatus { ready, degraded, failed, blocked, off }

class FeatureReadiness {
  FeatureReadiness({
    required this.id,
    required this.label,
    required this.status,
    this.requires = const [],
    this.details,
    this.reason,
  });

  final String id;
  final String label;
  final ReadinessStatus status;
  final List<String> requires;
  final String? details;
  final String? reason;

  /// The value under `features["<id>"]`. `id` is the map key, so it is not
  /// repeated here; `label` is a display hint kept out of the wire shape so the
  /// per-feature value is byte-identical across every kit.
  Map<String, dynamic> toJson() => {
        'status': status.name,
        if (requires.isNotEmpty) 'requires': requires,
        if (details != null) 'details': details,
        if (reason != null) 'reason': reason,
      };
}

/// A native library check result. ironmcp owns this SHAPE; the actual FFI probe
/// (`DynamicLibrary.open` + `lookup(symbol)`) is supplied by the app, so the kit
/// carries no dart:ffi dependency.
class LibraryStatus {
  LibraryStatus({
    required this.name,
    required this.loaded,
    this.symbolsChecked = 0,
    this.symbolsOk = 0,
    this.error,
  });

  final String name;
  final bool loaded;
  final int symbolsChecked;
  final int symbolsOk;
  final String? error;

  /// The value under `dependencies["<name>"]`. `name` is the map key. The symbol
  /// counts are FFI-specific, so they appear ONLY when a probe ran — a non-native
  /// dependency (a service, a database) just carries `loaded` and an optional
  /// `error`, which keeps `dependencies` meaningful for every kind of server.
  Map<String, dynamic> toJson() => {
        'loaded': loaded,
        if (symbolsChecked > 0) 'symbols_checked': symbolsChecked,
        if (symbolsChecked > 0) 'symbols_ok': symbolsOk,
        if (error != null) 'error': error,
      };
}

class DataFileStatus {
  DataFileStatus({required this.label, required this.found, this.path});

  final String label;
  final bool found;
  final String? path;

  /// The value under `data_files["<label>"]`. `label` is the map key.
  Map<String, dynamic> toJson() =>
      {'found': found, if (path != null) 'path': path};
}

/// A full readiness report. ironmcp owns the shape + the verdict semantics; the
/// app supplies the feature/lib/data checks.
class ReadinessReport {
  ReadinessReport({
    required this.appVersion,
    this.nativeVersion,
    this.features = const [],
    this.libs = const [],
    this.dataFiles = const [],
    this.platform = const {},
  });

  final String appVersion;
  final String? nativeVersion;
  final List<FeatureReadiness> features;
  final List<LibraryStatus> libs;
  final List<DataFileStatus> dataFiles;
  final Map<String, dynamic> platform;

  /// Overall verdict from the features that COUNT — `blocked`/`off` are excluded
  /// (invariant #7). failed > degraded > ready.
  ReadinessStatus get overallStatus {
    final counted = features.where((f) =>
        f.status != ReadinessStatus.blocked && f.status != ReadinessStatus.off);
    if (counted.any((f) => f.status == ReadinessStatus.failed)) {
      return ReadinessStatus.failed;
    }
    if (counted.any((f) => f.status == ReadinessStatus.degraded)) {
      return ReadinessStatus.degraded;
    }
    return ReadinessStatus.ready;
  }

  /// The wire shape. Learned from the ecosystem's health-check convention
  /// (IETF health-check draft / Kubernetes / Spring Actuator all key on `status`)
  /// and from loqu8's map-by-id structure: `features`, `dependencies`, and
  /// `data_files` are OBJECTS keyed by id/name — an agent reads
  /// `features["<id>"].status` in one hop, there is no list order to keep
  /// byte-identical across kits, and duplicate ids cannot hide. `dependencies`
  /// (not `libs`) so a server with services rather than native libraries is not
  /// misdescribed.
  Map<String, dynamic> toJson() => {
        'app_version': appVersion,
        if (nativeVersion != null) 'native_version': nativeVersion,
        'status': overallStatus.name,
        'features': {for (final f in features) f.id: f.toJson()},
        'dependencies': {for (final l in libs) l.name: l.toJson()},
        'data_files': {for (final d in dataFiles) d.label: d.toJson()},
        'platform': platform,
      };
}
