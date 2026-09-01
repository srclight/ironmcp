import 'dart:io';

import 'package:ironmcp/ironmcp.dart';
import 'package:test/test.dart';

void main() {
  late Directory dir;
  setUp(() async => dir = await Directory.systemTemp.createTemp('ironmcp_reg'));
  tearDown(() async => dir.delete(recursive: true));

  test('concurrent registers do not lose an entry (lock closes TOCTOU, #9)',
      () async {
    final reg = IronMcpRegistry(dir: dir, isPidAlive: (_) => true);
    await Future.wait([
      reg.register(IronMcpEntry(id: 'a', namespace: 'test', pid: 1)),
      reg.register(IronMcpEntry(id: 'b', namespace: 'test', pid: 2)),
      reg.register(IronMcpEntry(id: 'c', namespace: 'test', pid: 3)),
      reg.register(IronMcpEntry(id: 'd', namespace: 'test', pid: 4)),
    ]);
    final live = await reg.discover();
    expect(live.map((e) => e.id).toSet(), {'a', 'b', 'c', 'd'});
  });

  test('discover prunes a dead pid and rewrites the file (lazy GC, #10)',
      () async {
    final reg = IronMcpRegistry(dir: dir, isPidAlive: (pid) => pid != 2);
    await reg.register(IronMcpEntry(id: 'a', namespace: 'test', pid: 1));
    await reg.register(IronMcpEntry(id: 'b', namespace: 'test', pid: 2)); // dead
    expect((await reg.discover()).map((e) => e.id).toSet(), {'a'});
    // rewritten: a second discover still only sees the live one
    expect((await reg.discover()).map((e) => e.id).toSet(), {'a'});
  });

  test('unregister removes an entry', () async {
    final reg = IronMcpRegistry(dir: dir, isPidAlive: (_) => true);
    await reg.register(IronMcpEntry(id: 'a', namespace: 'test', pid: 1));
    await reg.unregister('a');
    expect(await reg.discover(), isEmpty);
  });

  test('entry JSON is language-neutral and carries NO hand-kept tool list (#3)',
      () {
    final j = IronMcpEntry(
      id: 'x',
      namespace: 'ns',
      pid: 9,
      host: '127.0.0.1',
      port: 8080,
      transport: 'http',
      version: '1.0',
      codeSha: 'abc123',
      capabilities: {'tools': <String, dynamic>{}},
    ).toJson();
    expect(j['code_sha'], 'abc123');
    expect(j['started_at'], isA<String>());
    expect(j.containsKey('tools'), isFalse); // honesty: no drifting count
    final e = IronMcpEntry.fromJson(j);
    expect(e.id, 'x');
    expect(e.port, 8080);
    expect(e.transport, 'http');
  });

  // GAP: the capabilities map's fromJson->toJson SURVIVAL was never asserted —
  // the JSON test above only checks it serializes on the way out. Prove a
  // non-empty, nested capabilities map round-trips through fromJson unchanged.
  test('capabilities round-trip through fromJson->toJson unchanged', () {
    final caps = {
      'strict_args': true,
      'ironmcp': true,
      'tools': <String, dynamic>{'count': 16},
    };
    final entry = IronMcpEntry(id: 'y', namespace: 'ns', pid: 7, capabilities: caps);
    final revived = IronMcpEntry.fromJson(entry.toJson());
    expect(revived.capabilities, caps); // parsed back into the object
    expect(revived.toJson()['capabilities'], caps); // and re-emitted intact
  });

  // GAP: an entry constructed with NO capabilities still emits an (empty) map,
  // and that empty map survives the round-trip — capabilities is never dropped.
  test('a default entry emits an empty capabilities map that round-trips', () {
    final j = IronMcpEntry(id: 'z', namespace: 'ns', pid: 8).toJson();
    expect(j['capabilities'], <String, dynamic>{});
    expect(IronMcpEntry.fromJson(j).capabilities, <String, dynamic>{});
  });

  // TASK 2 — the CANONICAL registry started_at format. Every ironmcp kit MUST
  // emit this exact shape so registry.json is byte-identical across languages:
  // ISO-8601 UTC, MILLISECOND precision (exactly 3 fractional digits), trailing
  // Z — e.g. 2026-09-01T10:35:34.123Z. NOT a +00:00 offset; NOT 6-digit micros.
  final canonical = RegExp(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$');

  test('isoMillisUtc emits exactly 3 fractional digits + Z (no offset)', () {
    // A microsecond-bearing instant is where Dart\'s own toIso8601String() would
    // blow out to 6 digits — the exact drift this normalisation fixes.
    final dt = DateTime.utc(2026, 9, 1, 10, 35, 34, 123, 456);
    expect(isoMillisUtc(dt), '2026-09-01T10:35:34.123Z');
    expect(canonical.hasMatch(isoMillisUtc(dt)), isTrue);
    // Micros are TRUNCATED (floored), never rounded: .123456 -> .123, .999999 -> .999.
    expect(isoMillisUtc(DateTime.utc(2026, 9, 1, 0, 0, 0, 999, 999)),
        '2026-09-01T00:00:00.999Z');
  });

  test('isoMillisUtc zero-pads every field and converts local to UTC', () {
    expect(isoMillisUtc(DateTime.utc(1, 2, 3, 4, 5, 6, 7)),
        '0001-02-03T04:05:06.007Z');
    // A non-UTC input is normalised to UTC before formatting.
    final local = DateTime.utc(2026, 1, 1, 12, 0, 0).toLocal();
    expect(isoMillisUtc(local), '2026-01-01T12:00:00.000Z');
  });

  test('entry started_at is the canonical millisecond-Z string, no +00:00', () {
    final j = IronMcpEntry(
      id: 'x',
      namespace: 'ns',
      pid: 9,
      startedAt: DateTime.utc(2026, 9, 1, 10, 35, 34, 123, 456),
    ).toJson();
    expect(j['started_at'], '2026-09-01T10:35:34.123Z');
    expect((j['started_at'] as String).contains('+00:00'), isFalse);
  });

  test('a default (now) entry still matches the canonical shape', () {
    final j = IronMcpEntry(id: 'x', namespace: 'ns', pid: 9).toJson();
    expect(canonical.hasMatch(j['started_at'] as String), isTrue,
        reason: 'default started_at must be YYYY-MM-DDTHH:mm:ss.SSSZ');
  });

  test('started_at round-trips: fromJson(toJson) re-emits the same string', () {
    final entry = IronMcpEntry(
      id: 'x',
      namespace: 'ns',
      pid: 9,
      startedAt: DateTime.utc(2026, 9, 1, 10, 35, 34, 123, 456),
    );
    final s1 = entry.toJson()['started_at'];
    final s2 = IronMcpEntry.fromJson(entry.toJson()).toJson()['started_at'];
    expect(s1, '2026-09-01T10:35:34.123Z');
    expect(s2, s1); // parse then re-emit is a fixed point
  });

  // GAP (canonical fix #3): the previous prune test could pass even if the
  // _write(map) on prune were deleted, because the second discover re-prunes in
  // memory. PROVE persistence: after a prune, a FRESH registry that considers
  // EVERY pid alive must still not see the dead entry — it can only be gone if
  // discover() actually rewrote registry.json to disk.
  test('discover PERSISTS the prune to disk (fresh reader sees it gone, #10)',
      () async {
    final writer = IronMcpRegistry(dir: dir, isPidAlive: (pid) => pid != 2);
    await writer.register(IronMcpEntry(id: 'a', namespace: 'test', pid: 1));
    await writer.register(IronMcpEntry(id: 'b', namespace: 'test', pid: 2)); // dead
    expect((await writer.discover()).map((e) => e.id).toSet(), {'a'});

    // A brand-new reader, treating ALL pids as alive, reads registry.json from
    // disk. If the prune had NOT been rewritten, 'b' would still be on disk and
    // this reader would resurrect it. It must not.
    final fresh = IronMcpRegistry(dir: dir, isPidAlive: (_) => true);
    expect((await fresh.discover()).map((e) => e.id).toSet(), {'a'},
        reason: 'the dead entry must be gone FROM DISK, not just re-pruned');
    // And the file on disk literally no longer names the dead pid.
    final onDisk = await File('${dir.path}/registry.json').readAsString();
    expect(onDisk.contains('"pid": 2'), isFalse);
  });

  // GAP (canonical fix #5): a corrupt or whitespace-only registry.json must
  // start fresh, not crash, on both discover() and register().
  test('a corrupt registry.json recovers (discover starts fresh, no crash)',
      () async {
    await Directory(dir.path).create(recursive: true);
    await File('${dir.path}/registry.json').writeAsString('{ this is not json');
    final reg = IronMcpRegistry(dir: dir, isPidAlive: (_) => true);
    expect(await reg.discover(), isEmpty); // recovered, not thrown
    // …and a register onto the corrupt file succeeds and yields a clean store.
    await reg.register(IronMcpEntry(id: 'a', namespace: 'test', pid: 1));
    expect((await reg.discover()).map((e) => e.id).toSet(), {'a'});
  });

  test('a whitespace-only registry.json is treated as empty, not a crash',
      () async {
    await Directory(dir.path).create(recursive: true);
    await File('${dir.path}/registry.json').writeAsString('   \n\t  ');
    final reg = IronMcpRegistry(dir: dir, isPidAlive: (_) => true);
    expect(await reg.discover(), isEmpty);
  });

  // GAP: a stale lock left by a crashed holder is stolen past staleLockAfter.
  test('a stale lock (older than staleLockAfter) is stolen so a register proceeds',
      () async {
    await Directory(dir.path).create(recursive: true);
    final lock = File('${dir.path}/registry.json.lock');
    await lock.create();
    // Backdate the lock so it looks abandoned by a crashed process.
    await lock.setLastModified(DateTime.now().subtract(const Duration(minutes: 5)));
    final reg = IronMcpRegistry(
      dir: dir,
      isPidAlive: (_) => true,
      staleLockAfter: const Duration(seconds: 1),
      lockTimeout: const Duration(seconds: 2),
    );
    await reg.register(IronMcpEntry(id: 'a', namespace: 'test', pid: 1));
    expect((await reg.discover()).map((e) => e.id).toSet(), {'a'});
  });

  // GAP: when the lock is held and NOT stale, the writer proceeds best-effort at
  // the lockTimeout deadline rather than hanging forever.
  test('a held (fresh) lock: register proceeds best-effort at lockTimeout',
      () async {
    await Directory(dir.path).create(recursive: true);
    final lock = File('${dir.path}/registry.json.lock');
    await lock.create(); // held, fresh mtime -> never stolen within the window
    final reg = IronMcpRegistry(
      dir: dir,
      isPidAlive: (_) => true,
      staleLockAfter: const Duration(hours: 1),
      lockTimeout: const Duration(milliseconds: 80),
    );
    final sw = Stopwatch()..start();
    await reg.register(IronMcpEntry(id: 'a', namespace: 'test', pid: 1));
    sw.stop();
    expect(sw.elapsedMilliseconds, greaterThanOrEqualTo(60)); // waited the deadline
    expect((await reg.discover()).map((e) => e.id).toSet(), {'a'}); // wrote anyway
  });

  // GAP: fromJson with a missing or unparseable started_at defaults to now
  // (a canonical millisecond-Z shape), never throwing.
  test('fromJson defaults a missing started_at to a canonical now-timestamp', () {
    final e = IronMcpEntry.fromJson({'id': 'x', 'namespace': 'ns', 'pid': 9});
    final s = e.toJson()['started_at'] as String;
    expect(canonical.hasMatch(s), isTrue);
    // Defaulted to ~now, well after an obviously-old sentinel.
    expect(e.startedAt.isAfter(DateTime.utc(2000)), isTrue);
  });

  test('fromJson defaults an UNPARSEABLE started_at to now, not a crash', () {
    final e = IronMcpEntry.fromJson(
        {'id': 'x', 'namespace': 'ns', 'pid': 9, 'started_at': 'not-a-date'});
    expect(canonical.hasMatch(e.toJson()['started_at'] as String), isTrue);
  });

  // GAP: register() with an existing id OVERWRITES rather than duplicating.
  test('register with an existing id overwrites (last write wins)', () async {
    final reg = IronMcpRegistry(dir: dir, isPidAlive: (_) => true);
    await reg.register(IronMcpEntry(id: 'a', namespace: 'test', pid: 1, port: 8080));
    await reg.register(IronMcpEntry(id: 'a', namespace: 'test', pid: 2, port: 9090));
    final live = await reg.discover();
    expect(live.length, 1); // one entry, not two
    expect(live.single.pid, 2); // the second registration won
    expect(live.single.port, 9090);
  });
}
