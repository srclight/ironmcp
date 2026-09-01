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

  test('StrictMcpServer is a drop-in McpServer that registers hardened tools', () {
    final server = StrictMcpServer(
      Implementation(name: 'test', version: '0.0.0'),
      options: McpServerOptions(
        capabilities: ServerCapabilities(tools: ServerCapabilitiesTools()),
      ),
    );
    expect(server, isA<McpServer>()); // drop-in for any McpServer call site
    final reg = server.registerTool(
      'echo',
      inputSchema: ToolInputSchema(properties: {'a': JsonSchema.string()}),
      callback: (args, extra) =>
          CallToolResult(content: [TextContent(text: 'ok')]),
    );
    expect(reg, isNotNull); // override ran, stamped + guarded, delegated cleanly
  });

  // GAP: stamp reconstructs the ToolInputSchema when closing it — the `required`
  // list must survive, or a closed schema silently drops its required-arg
  // constraint.
  test('stamp PRESERVES the required list when it closes the schema', () {
    final stamped = Harden.stamp(schema)!.toJson();
    expect(stamped['additionalProperties'], isFalse);
    expect(stamped['required'], ['a']); // not lost in reconstruction
    expect((stamped['properties'] as Map).keys, containsAll(['a', 'b']));
  });

  // GAP: a malformed schema whose properties is not a map must NOT be stamped
  // closed (canonical fix #4 — enforce only when introspectable). ToolInputSchema
  // is typed, so this is exercised via StrictArgs.stampClosed on a raw schema in
  // strict_args_test; here we pin that a null schema stays null and an opted-open
  // one is untouched (already covered above), and add the composition API below.

  // GAP: the HardenedServer composition wrapper and the harden() factory had ZERO
  // tests — the callback-wrapping refusal path on the composition API was
  // entirely unverified. Invoke the WRAPPED callback directly (no transport).
  RequestHandlerExtra dummyExtra() => RequestHandlerExtra(
        signal: BasicAbortController().signal,
        requestId: 1,
        sendNotification: (n, {relatedTask}) async {},
        sendRequest: <T extends BaseResultData>(req, factory, opts) async =>
            throw UnimplementedError(),
      );

  McpServer plainServer() => McpServer(
        Implementation(name: 'comp', version: '0.0.0'),
        options: McpServerOptions(
          capabilities: ServerCapabilities(tools: ServerCapabilitiesTools()),
        ),
      );

  test('harden() returns a HardenedServer wrapping the given inner server', () {
    final inner = plainServer();
    final h = harden(inner);
    expect(h, isA<HardenedServer>());
    expect(identical(h.inner, inner), isTrue);
  });

  test('HardenedServer advertises the schema CLOSED on the registered tool', () {
    final h = harden(plainServer());
    final reg = h.registerTool(
      'echo',
      inputSchema: ToolInputSchema(properties: {'a': JsonSchema.string()}),
      callback: (args, extra) =>
          CallToolResult(content: [TextContent(text: 'ok')]),
    );
    expect(reg.inputSchema!.toJson()['additionalProperties'], isFalse);
  });

  test('HardenedServer WRAPS the callback: an undeclared arg is refused, body never runs',
      () async {
    final h = harden(plainServer());
    var ran = 0;
    final reg = h.registerTool(
      'echo',
      inputSchema: ToolInputSchema(properties: {'a': JsonSchema.string()}),
      callback: (args, extra) {
        ran++;
        return CallToolResult(content: [TextContent(text: 'ok')]);
      },
    );
    final fn = (reg.callback as FunctionToolCallback).function;
    final refused = await fn({'a': 'x', 'sneaky': 'p@ssw0rd'}, dummyExtra());
    expect(refused.isError, isTrue);
    expect((refused.content.first as TextContent).text,
        isNot(contains('p@ssw0rd'))); // value never echoed
    expect(ran, 0); // the wrapper stopped it BEFORE the body

    // …and a clean call still reaches the body on the same wrapped tool.
    final ok = await fn({'a': 'x'}, dummyExtra());
    expect(ok.isError, isFalse);
    expect(ran, 1);
  });

  test('HardenedServer honours a custom reconnect hint in the wrapped refusal',
      () async {
    final h = harden(plainServer(), reconnectHint: 'reconnect via pack_status');
    final reg = h.registerTool(
      'echo',
      inputSchema: ToolInputSchema(properties: {'a': JsonSchema.string()}),
      callback: (args, extra) =>
          CallToolResult(content: [TextContent(text: 'ok')]),
    );
    final fn = (reg.callback as FunctionToolCallback).function;
    final refused = await fn({'bad': 1}, dummyExtra());
    expect((refused.content.first as TextContent).text,
        contains('reconnect via pack_status'));
  });
}
