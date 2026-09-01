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
}
