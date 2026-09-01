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

  // GAP: the SYNCHRONOUS fence — _done is set before the first await, so a second
  // run() entered while the first is still in flight is an immediate no-op (not
  // just idempotent AFTER completion). A concurrent shutdown trigger cannot
  // double-run the sequence.
  test('a second run BEFORE the first completes is a synchronous no-op (#6)',
      () async {
    final gate = Completer<void>();
    var runs = 0;
    final q = CleanQuit([
      () async {
        runs++;
        await gate.future; // hold the first run open
      },
    ]);
    final first = q.run(); // enters, runs the step to its await, sets _done
    expect(runs, 1);
    expect(q.hasRun, isTrue); // fenced synchronously, before the first finishes
    await q.run(); // _done already set -> returns at once, does NOT re-run
    expect(runs, 1);
    gate.complete();
    await first;
    expect(runs, 1);
  });

  // GAP: multiple throwing steps — every failure is reported and NONE aborts the
  // rest (the fence holds across more than one throw).
  test('every throwing step is reported and the sequence runs to the end',
      () async {
    final order = <int>[];
    final errored = <int>[];
    await CleanQuit(
      [
        () async => throw StateError('a'),
        () async => order.add(1),
        () async => throw StateError('b'),
        () async => order.add(3),
      ],
      onError: (i, e) => errored.add(i),
    ).run();
    expect(order, [1, 3]);
    expect(errored, [0, 2]); // both failing indices reported
  });

  // GAP (canonical fix #2): the onError handler is ITSELF fenced — a reporter
  // that throws must NOT strand the remaining shutdown steps.
  test('an onError that itself throws does NOT abort the remaining steps',
      () async {
    final order = <int>[];
    await CleanQuit(
      [
        () async => order.add(1),
        () async => throw StateError('boom'),
        () async => order.add(3),
      ],
      onError: (i, e) => throw StateError('the reporter blew up too'),
    ).run();
    expect(order, [1, 3]); // step after the throw still ran
  });

  // GAP: a throwing step with a DEFAULT/ABSENT onError is swallowed, not fatal.
  test('a throwing step with no onError is swallowed; the rest still run',
      () async {
    final order = <int>[];
    await CleanQuit([
      () async => order.add(1),
      () async => throw StateError('boom'),
      () async => order.add(3),
    ]).run();
    expect(order, [1, 3]);
  });
}
