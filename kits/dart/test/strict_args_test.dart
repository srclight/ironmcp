import 'package:ironmcp/ironmcp.dart';
import 'package:test/test.dart';

void main() {
  final withProps = {
    'type': 'object',
    'properties': {'a': <String, Object?>{}, 'b': <String, Object?>{}},
  };
  final zeroArg = {'type': 'object', 'properties': <String, Object?>{}};

  test('state 2: an unknown key is refused, named, not echoed', () {
    final r = StrictArgs.check(withProps, {'a': 1, 'typo': 2}, toolName: 'echo');
    expect(r.ok, isFalse);
    expect(r.unknown, ['typo']);
    expect(r.message, contains('unknown argument'));
    expect(r.message, isNot(contains('2'))); // value never echoed
  });

  test('state 2: known keys pass', () {
    expect(StrictArgs.check(withProps, {'a': 1, 'b': 2}).ok, isTrue);
  });

  test('state 2: a zero-arg tool refuses extras', () {
    expect(StrictArgs.check(zeroArg, {'typo': 1}).ok, isFalse);
  });

  test('state 1: no properties is permissive', () {
    expect(StrictArgs.check({'type': 'object'}, {'whatever': 1}).ok, isTrue);
  });

  test('state 3: additionalProperties:true opts out', () {
    final s = {
      'type': 'object',
      'properties': {'a': <String, Object?>{}},
      'additionalProperties': true,
    };
    expect(StrictArgs.check(s, {'a': 1, 'x': 2}).ok, isTrue);
  });

  test('null schema is permissive', () {
    expect(StrictArgs.check(null, {'x': 1}).ok, isTrue);
  });

  test('stampClosed stamps when enforced', () {
    expect(StrictArgs.stampClosed(withProps)!['additionalProperties'], isFalse);
    expect(StrictArgs.stampClosed(zeroArg)!['additionalProperties'], isFalse);
  });

  test('stampClosed leaves opted-open and unintrospectable schemas alone', () {
    final open = {
      'type': 'object',
      'properties': {'a': <String, Object?>{}},
      'additionalProperties': true,
    };
    expect(identical(StrictArgs.stampClosed(open), open), isTrue);
    final bare = {'type': 'object'};
    expect(identical(StrictArgs.stampClosed(bare), bare), isTrue);
  });

  // GAP: the unknown list is sorted — multi-key refusals must be deterministic
  // and alphabetical, not insertion-ordered.
  test('multiple unknown keys are reported sorted (deterministic)', () {
    final r = StrictArgs.check(withProps, {'zebra': 1, 'apple': 2, 'mango': 3});
    expect(r.ok, isFalse);
    expect(r.unknown, ['apple', 'mango', 'zebra']);
    // The message lists them in the same sorted order.
    expect(r.message, contains('apple, mango, zebra'));
  });

  // GAP: the >10-key cap in the message must bound BOTH the unknown list and the
  // accepted list so a hostile/huge payload cannot turn the guard into an
  // amplifier. Exactly 10 listed, then "… (N more)".
  test('the message caps a >10 unknown list at 10 with a "(N more)" tail', () {
    final args = {for (var i = 0; i < 13; i++) 'k${i.toString().padLeft(2, '0')}': i};
    final r = StrictArgs.check(withProps, args);
    expect(r.ok, isFalse);
    expect(r.unknown.length, 13); // the structured list is complete…
    expect(r.message, contains('… (3 more)')); // …the PROSE is bounded
    expect(r.message, contains('k00, k01, k02, k03, k04, k05, k06, k07, k08, k09'));
    expect(r.message, isNot(contains('k10,'))); // the 11th is folded into the tail
  });

  test('the message caps a >10 accepted list at 10 with a "(N more)" tail', () {
    final wide = {
      'type': 'object',
      'properties': {for (var i = 0; i < 15; i++) 'p${i.toString().padLeft(2, '0')}': <String, Object?>{}},
    };
    final r = StrictArgs.check(wide, {'typo': 1});
    expect(r.ok, isFalse);
    expect(r.accepted.length, 15);
    expect(r.message, contains('… (5 more)')); // accepted side is bounded too
  });

  // GAP: the reconnect hint is part of the recoverable-error contract — the
  // default text must appear, and a custom hint must pass through unchanged.
  test('the default reconnect hint appears in the refusal message', () {
    final r = StrictArgs.check(withProps, {'typo': 1});
    expect(r.message, contains(Messages.defaultReconnectHint));
    expect(r.message, contains('reconnect the MCP'));
  });

  test('a custom reconnect hint passes through into the message', () {
    final r = StrictArgs.check(withProps, {'typo': 1},
        reconnectHint: 'call pack_status then reconnect');
    expect(r.message, contains('call pack_status then reconnect'));
    expect(r.message, isNot(contains(Messages.defaultReconnectHint)));
  });

  // GAP: the zero-accepted refusal prose ("accepts no arguments.") and the
  // "Nothing was executed." clause are load-bearing but were never asserted.
  test('a zero-arg refusal states "accepts no arguments" and "Nothing was executed"',
      () {
    final r = StrictArgs.check(zeroArg, {'typo': 1}, toolName: 'ping');
    expect(r.ok, isFalse);
    expect(r.message, contains("Tool 'ping' accepts no arguments."));
    expect(r.message, contains('Nothing was executed.'));
  });

  test('a non-empty refusal lists what the tool DOES accept', () {
    final r = StrictArgs.check(withProps, {'typo': 1}, toolName: 'echo');
    expect(r.message, contains("Tool 'echo' accepts: a, b."));
    expect(r.message, contains('Nothing was executed.'));
  });

  // GAP (canonical fix #4): a malformed schema whose `properties` is PRESENT but
  // NOT a map is UNINTROSPECTABLE, so the guard must fall back to permissive —
  // it must NOT refuse every argument because it could not read the shape.
  test('malformed schema: properties as a String is permissive, not all-refusing',
      () {
    final s = {'type': 'object', 'properties': 'oops'};
    expect(StrictArgs.check(s, {'anything': 1, 'more': 2}).ok, isTrue);
    // …and it is never stamped closed either.
    expect(identical(StrictArgs.stampClosed(s), s), isTrue);
  });

  test('malformed schema: properties as a List is permissive, not all-refusing',
      () {
    final s = {
      'type': 'object',
      'properties': ['a', 'b'],
    };
    expect(StrictArgs.check(s, {'x': 1}).ok, isTrue);
    expect(identical(StrictArgs.stampClosed(s), s), isTrue);
  });
}
