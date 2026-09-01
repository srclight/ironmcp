import 'dart:async';

import 'package:ironmcp/ironmcp.dart';
import 'package:test/test.dart';

void main() {
  test('steps run in order', () async {
    final order = <int>[];
    await CleanQuit([
      () async => order.add(1),
      () async => order.add(2),
      () async => order.add(3),
    ]).run();
    expect(order, [1, 2, 3]);
  });

  test('a throwing step does not abort the rest (invariant #5-safe)', () async {
    final order = <int>[];
    final errored = <int>[];
    await CleanQuit(
      [
        () async => order.add(1),
        () async => throw StateError('boom'),
        () async => order.add(3),
      ],
      onError: (i, e) => errored.add(i),
    ).run();
    expect(order, [1, 3]);
    expect(errored, [1]); // the throwing step's index
  });

  test('second run is a no-op (idempotent, invariant #6)', () async {
    var count = 0;
    final q = CleanQuit([() async => count++]);
    await q.run();
    await q.run();
    expect(count, 1);
    expect(q.hasRun, isTrue);
  });

  test('replyThenQuit returns the result BEFORE the quit fires (invariant #1)',
      () async {
    final fired = Completer<void>();
    var quitFired = false;
    final r = replyThenQuit(
      'reply',
      () async {
        quitFired = true;
        fired.complete();
      },
      delay: Duration.zero,
    );
    expect(r, 'reply');
    expect(quitFired, isFalse); // reply returned first; quit not yet fired
    await fired.future;
    expect(quitFired, isTrue);
  });
}
