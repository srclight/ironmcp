import 'dart:io';

import 'package:ironmcp/ironmcp.dart';
import 'package:test/test.dart';

void main() {
  test('start retries on SocketException then succeeds (invariant #2)', () async {
    var calls = 0;
    final d = IronMcpDaemon(
      bind: () async {
        calls++;
        if (calls < 3) throw const SocketException('busy');
      },
      retryDelay: Duration.zero,
    );
    expect(await d.start(), isTrue);
    expect(calls, 3);
    expect(d.isRunning, isTrue);
    expect(d.lastError, isNull);
  });

  test('start gives up after maxRetries — non-fatal, sets lastError', () async {
    var calls = 0;
    final d = IronMcpDaemon(
      bind: () async {
        calls++;
        throw const SocketException('busy');
      },
      retryDelay: Duration.zero,
    );
    expect(await d.start(), isFalse); // does NOT throw
    expect(calls, 3);
    expect(d.isRunning, isFalse);
    expect(d.lastError, isA<SocketException>());
  });

  test('a non-socket error fails fast (no retry) and is non-fatal', () async {
    var calls = 0;
    final d = IronMcpDaemon(
      bind: () async {
        calls++;
        throw StateError('boom');
      },
      retryDelay: Duration.zero,
    );
    expect(await d.start(), isFalse);
    expect(calls, 1);
    expect(d.lastError, isA<StateError>());
  });

  test('stop runs unbind and clears isRunning; safe when not running', () async {
    var unbound = 0;
    final d = IronMcpDaemon(
      bind: () async {},
      unbind: () async => unbound++,
      retryDelay: Duration.zero,
    );
    await d.start();
    expect(d.isRunning, isTrue);
    await d.stop();
    expect(d.isRunning, isFalse);
    expect(unbound, 1);
    await d.stop(); // no throw when already stopped
    expect(d.isRunning, isFalse);
  });

  // GAP: the onLog retry-message callback was never asserted to fire, and a
  // non-default maxRetries was never used. Prove BOTH: a custom cap of 5 retries
  // and an onLog that fires once per inter-attempt wait, naming the attempt.
  test('onLog fires the retry message once per wait, honouring a custom maxRetries',
      () async {
    final logs = <String>[];
    var calls = 0;
    final d = IronMcpDaemon(
      bind: () async {
        calls++;
        throw const SocketException('busy');
      },
      maxRetries: 5,
      retryDelay: Duration.zero,
      onLog: logs.add,
    );
    expect(await d.start(), isFalse);
    expect(calls, 5); // custom cap honoured, not the default 3
    // onLog fires between attempts only — 5 attempts -> 4 waits -> 4 messages.
    expect(logs.length, 4);
    expect(logs.first, contains('attempt 1/5'));
    expect(logs.last, contains('attempt 4/5'));
    for (final m in logs) {
      expect(m, contains('bind busy'));
    }
  });

  test('a successful first bind logs nothing (no spurious retry message)', () async {
    final logs = <String>[];
    final d = IronMcpDaemon(
      bind: () async {},
      retryDelay: Duration.zero,
      onLog: logs.add,
    );
    expect(await d.start(), isTrue);
    expect(logs, isEmpty);
  });

  // GAP: the retryDelay wait between attempts was never exercised with a
  // non-zero duration. Prove the daemon actually WAITS retryDelay between
  // attempts (a real inter-attempt pause elapses).
  test('a non-zero retryDelay is actually awaited between attempts', () async {
    var calls = 0;
    final d = IronMcpDaemon(
      bind: () async {
        calls++;
        if (calls < 2) throw const SocketException('busy');
      },
      maxRetries: 2,
      retryDelay: const Duration(milliseconds: 60),
    );
    final sw = Stopwatch()..start();
    expect(await d.start(), isTrue);
    sw.stop();
    expect(calls, 2);
    // One wait of ~60ms happened between the two attempts.
    expect(sw.elapsedMilliseconds, greaterThanOrEqualTo(50));
  });
}
