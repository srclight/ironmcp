import 'package:ironmcp/ironmcp.dart';
import 'package:mcp_dart/mcp_dart.dart';
import 'package:test/test.dart';

void main() {
  final schema = ToolInputSchema(
    properties: {'a': JsonSchema.string(), 'b': JsonSchema.integer()},
    required: ['a'],
  );
  final zeroArg = ToolInputSchema(properties: {});

  test('stamp advertises additionalProperties:false when enforced', () {
    expect(Harden.stamp(schema)!.toJson()['additionalProperties'], isFalse);
    expect(Harden.stamp(zeroArg)!.toJson()['additionalProperties'], isFalse);
  });

  test('stamp leaves an opted-open or null schema alone', () {
    final open = ToolInputSchema(
      properties: {'a': JsonSchema.string()},
      additionalProperties: true,
    );
    expect(Harden.stamp(open)!.toJson()['additionalProperties'], isTrue);
    expect(Harden.stamp(null), isNull);
  });

  test('refusalFor refuses an unknown key, names it, and NEVER echoes the value',
      () {
    final r = Harden.refusalFor('echo', schema, {'a': 'x', 'secret': 'p@ssw0rd'});
    expect(r, isNotNull);
    expect(r!.isError, isTrue);
    final iron = r.structuredContent!['ironmcp'] as Map;
    expect(iron['refused'], isTrue);
    expect(iron['unknown'], ['secret']);
    expect(iron['tool'], 'echo');
    final text = (r.content.first as TextContent).text;
    expect(text, contains('unknown argument'));
    expect(text, isNot(contains('p@ssw0rd'))); // STUBBY: value never echoed
  });

  test('refusalFor passes a clean call (returns null)', () {
    expect(Harden.refusalFor('echo', schema, {'a': 'x'}), isNull);
    expect(Harden.refusalFor('echo', schema, {'a': 'x', 'b': 1}), isNull);
  });

  test('K9: a zero-arg tool refuses any extra', () {
    expect(Harden.refusalFor('ping', zeroArg, {'x': 1}), isNotNull);
  });

  test('K9: an opted-open tool permits extras', () {
    final open = ToolInputSchema(
      properties: {'a': JsonSchema.string()},
      additionalProperties: true,
    );
    expect(Harden.refusalFor('open', open, {'a': 'x', 'y': 2}), isNull);
  });

  test('K9: an unintrospectable (null) schema is permissive, not a crash', () {
    expect(Harden.refusalFor('t', null, {'whatever': 1}), isNull);
  });
}
