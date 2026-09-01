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
}
