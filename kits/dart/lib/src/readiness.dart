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

  Map<String, dynamic> toJson() => {
        'id': id,
        'label': label,
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

  Map<String, dynamic> toJson() => {
        'name': name,
        'loaded': loaded,
        'symbols_checked': symbolsChecked,
        'symbols_ok': symbolsOk,
        if (error != null) 'error': error,
      };
}

class DataFileStatus {
  DataFileStatus({required this.label, required this.found, this.path});

  final String label;
  final bool found;
  final String? path;

  Map<String, dynamic> toJson() =>
      {'label': label, 'found': found, if (path != null) 'path': path};
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

  Map<String, dynamic> toJson() => {
        'app_version': appVersion,
        if (nativeVersion != null) 'native_version': nativeVersion,
        'overall_status': overallStatus.name,
        'features': features.map((f) => f.toJson()).toList(),
        'libs': libs.map((l) => l.toJson()).toList(),
        'data_files': dataFiles.map((d) => d.toJson()).toList(),
        'platform': platform,
      };
}
