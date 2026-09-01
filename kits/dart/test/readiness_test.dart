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
}
