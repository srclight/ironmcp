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
}
