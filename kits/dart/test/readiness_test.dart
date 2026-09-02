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

  test('toJson uses `status` + maps keyed by id/name (the standard shape)', () {
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
    expect(j['status'], 'ready'); // was `overall_status`
    // features / dependencies / data_files are OBJECTS keyed by id/name.
    expect(j['features'], isA<Map>());
    expect((j['features'] as Map)['a']['requires'], ['x']);
    expect((j['features'] as Map)['a'].containsKey('id'), isFalse); // id is the key
    expect(j.containsKey('libs'), isFalse); // renamed to `dependencies`
    expect((j['dependencies'] as Map)['libfoo']['symbols_ok'], 3);
    expect((j['data_files'] as Map)['dict']['found'], isTrue);
    expect((j['data_files'] as Map)['dict'].containsKey('label'), isFalse);
  });

  test('a dependency with no symbol probe omits the FFI symbol counts', () {
    // `dependencies` must stay meaningful for a service/db, not only native libs.
    final j = LibraryStatus(name: 'postgres', loaded: true).toJson();
    expect(j['loaded'], isTrue);
    expect(j.containsKey('symbols_checked'), isFalse);
    expect(j.containsKey('symbols_ok'), isFalse);
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

  // GAP: FeatureReadiness.toJson never serialized the optional `details`/`reason`
  // branches — both `if (x != null)` arms were uncovered. Pin the PRESENT arm.
  test('FeatureReadiness serializes details and reason when they are set', () {
    final j = FeatureReadiness(
      id: 'ffi',
      label: 'FFI',
      status: ReadinessStatus.degraded,
      requires: ['libnomad'],
      details: 'loaded 2 of 3 symbols',
      reason: 'optional symbol nomad_speak missing',
    ).toJson();
    expect(j['details'], 'loaded 2 of 3 symbols');
    expect(j['reason'], 'optional symbol nomad_speak missing');
    expect(j['requires'], ['libnomad']);
  });

  // GAP: the OMISSION arm — with details/reason (and an empty requires) null,
  // none of those keys appear in the JSON.
  test('FeatureReadiness omits details, reason, and empty requires', () {
    final j = FeatureReadiness(
      id: 'core',
      label: 'Core',
      status: ReadinessStatus.ready,
    ).toJson();
    expect(j.containsKey('details'), isFalse);
    expect(j.containsKey('reason'), isFalse);
    expect(j.containsKey('requires'), isFalse); // empty list is omitted, not []
    expect(j['status'], 'ready');
  });

  // GAP: DataFileStatus with found:false and an absent path — only the
  // found+path branch was asserted, so the `if (path != null)` omission arm was
  // uncovered. A missing data file must serialize found:false with NO path key.
  test('DataFileStatus omits path when the file was not found', () {
    final j = DataFileStatus(label: 'dict', found: false).toJson();
    expect(j.containsKey('label'), isFalse); // label is the map key, not in the value
    expect(j['found'], isFalse);
    expect(j.containsKey('path'), isFalse); // absent-path omission arm
  });

  test('DataFileStatus carries the path when the file was found', () {
    final j =
        DataFileStatus(label: 'dict', found: true, path: '/opt/data/dict.xdb')
            .toJson();
    expect(j['found'], isTrue);
    expect(j['path'], '/opt/data/dict.xdb');
  });
}
