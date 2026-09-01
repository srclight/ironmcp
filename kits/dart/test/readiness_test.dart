import 'package:ironmcp/ironmcp.dart';
import 'package:test/test.dart';

void main() {
  ReadinessReport report(List<FeatureReadiness> f) =>
      ReadinessReport(appVersion: '1', features: f);

  test('overall EXCLUDES blocked and off from the verdict (invariant #7)', () {
    final r = report([
      FeatureReadiness(id: 'a', label: 'A', status: ReadinessStatus.ready),
      FeatureReadiness(id: 'b', label: 'B', status: ReadinessStatus.blocked),
      FeatureReadiness(id: 'c', label: 'C', status: ReadinessStatus.off),
    ]);
    expect(r.overallStatus, ReadinessStatus.ready);
  });

  test('all blocked/off still yields ready (the dev-box case), not failed', () {
    final r = report([
      FeatureReadiness(id: 'a', label: 'A', status: ReadinessStatus.blocked),
      FeatureReadiness(id: 'b', label: 'B', status: ReadinessStatus.off),
    ]);
    expect(r.overallStatus, ReadinessStatus.ready);
  });

  test('a failed counted feature makes overall failed', () {
    expect(
      report([
        FeatureReadiness(id: 'a', label: 'A', status: ReadinessStatus.ready),
        FeatureReadiness(id: 'b', label: 'B', status: ReadinessStatus.failed),
      ]).overallStatus,
      ReadinessStatus.failed,
    );
  });

  test('a degraded feature (no failures) makes overall degraded', () {
    expect(
      report([
        FeatureReadiness(id: 'a', label: 'A', status: ReadinessStatus.degraded),
      ]).overallStatus,
      ReadinessStatus.degraded,
    );
  });

  test('toJson is stable snake_case with the computed verdict', () {
    final j = ReadinessReport(
      appVersion: '2.0',
      nativeVersion: '1.5',
      features: [
        FeatureReadiness(
            id: 'a',
            label: 'A',
            status: ReadinessStatus.ready,
            requires: ['x']),
      ],
      libs: [LibraryStatus(name: 'libfoo', loaded: true, symbolsChecked: 3, symbolsOk: 3)],
      dataFiles: [DataFileStatus(label: 'dict', found: true, path: '/x')],
      platform: {'os': 'linux'},
    ).toJson();
    expect(j['app_version'], '2.0');
    expect(j['overall_status'], 'ready');
    expect((j['libs'] as List).first['symbols_ok'], 3);
    expect((j['features'] as List).first['requires'], ['x']);
    expect((j['data_files'] as List).first['found'], isTrue);
  });

  // GAP: an empty feature list must report ready (nothing counted against it).
  test('an empty feature list yields ready (vacuously)', () {
    expect(report([]).overallStatus, ReadinessStatus.ready);
  });

  // GAP: failed OUTRANKS degraded when BOTH a failed and a degraded counted
  // feature are present — the precedence branch was never exercised directly.
  test('failed outranks degraded when both counted statuses are present', () {
    final r = report([
      FeatureReadiness(id: 'a', label: 'A', status: ReadinessStatus.degraded),
      FeatureReadiness(id: 'b', label: 'B', status: ReadinessStatus.failed),
      FeatureReadiness(id: 'c', label: 'C', status: ReadinessStatus.ready),
    ]);
    expect(r.overallStatus, ReadinessStatus.failed);
  });

  // GAP: the LibraryStatus.error non-null branch (a failed FFI probe) was
  // untested — it must serialize the error string.
  test('LibraryStatus carries the error string when a probe fails', () {
    final j = LibraryStatus(
      name: 'libnomad',
      loaded: false,
      error: 'dlopen: cannot open shared object file',
    ).toJson();
    expect(j['loaded'], isFalse);
    expect(j['error'], 'dlopen: cannot open shared object file');
  });

  test('LibraryStatus omits the error key when the probe succeeded', () {
    final j = LibraryStatus(name: 'libnomad', loaded: true).toJson();
    expect(j.containsKey('error'), isFalse);
  });
}
