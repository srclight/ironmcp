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
}
