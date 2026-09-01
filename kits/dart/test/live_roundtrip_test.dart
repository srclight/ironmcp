import 'dart:async';

import 'package:ironmcp/ironmcp.dart';
import 'package:mcp_dart/mcp_dart.dart';
import 'package:test/test.dart';

/// TASK 1 — LIVE ROUND-TRIP CONFORMANCE.
///
/// Pure unit tests (harden_test.dart) exercise `Harden.stamp` / `Harden.refusalFor`
/// in isolation. They CANNOT catch a transport-level regression: the mcp_dart
/// server validates the advertised (closed) schema itself, BEFORE a tool body
/// runs, and returns a JSON-RPC error / error-result. This is exactly the seam
/// the iCE runtime gate exposed. These tests drive a REAL client<->server MCP
/// session over an in-memory transport pair and prove advertisement == runtime
/// end to end:
///
///   * `tools/list` advertises `additionalProperties: false` over the wire;
///   * a valid `tools/call` RUNS the tool and returns its result;
///   * a `tools/call` carrying an UNDECLARED extra arg is REFUSED (the tool body
///     never runs) — whether the SDK rejects the closed schema with -32602 or
///     returns an error result, the call does not silently drop the extra.

/// One half of an in-memory transport pair. `send` hands the message straight to
/// the peer's `onmessage`, on a microtask so delivery is asynchronous like a real
/// socket (no synchronous re-entrancy into the sender's stack).
class _PairTransport extends Transport {
  _PairTransport(this._label);

  final String _label;
  _PairTransport? peer;
  var _closed = false;

  @override
  void Function()? onclose;
  @override
  void Function(Error error)? onerror;
  @override
  void Function(JsonRpcMessage message)? onmessage;

  @override
  String? get sessionId => null;

  @override
  Future<void> start() async {}

  @override
  Future<void> send(JsonRpcMessage message, {int? relatedRequestId}) async {
    if (_closed) throw StateError('$_label transport is closed');
    final p = peer;
    if (p == null) throw StateError('$_label transport has no peer');
    // Re-encode through JSON so the peer parses a wire-shaped message, exactly
    // as a socket/stdio transport would — nothing is passed by shared reference.
    final wire = JsonRpcMessage.fromJson(message.toJson());
    scheduleMicrotask(() {
      if (!p._closed) p.onmessage?.call(wire);
    });
  }

  @override
  Future<void> close() async {
    if (_closed) return;
    _closed = true;
    final p = peer;
    onclose?.call();
    if (p != null && !p._closed) unawaited(p.close());
  }

  static (_PairTransport, _PairTransport) linkedPair() {
    final a = _PairTransport('client');
    final b = _PairTransport('server');
    a.peer = b;
    b.peer = a;
    return (a, b);
  }
}

void main() {
  // A hardened server carrying one tool with a declared, closed object schema.
  // The callback records whether it actually ran so an undeclared-arg call can
  // be proven to have been stopped BEFORE the body.
  late StrictMcpServer server;
  late McpClient client;
  late int echoRuns;
  late Map<String, dynamic>? lastArgs;

  Future<void> wire() async {
    echoRuns = 0;
    lastArgs = null;
    server = StrictMcpServer(
      Implementation(name: 'iron-live', version: '0.0.0'),
      options: McpServerOptions(
        capabilities: ServerCapabilities(tools: ServerCapabilitiesTools()),
      ),
    );
    server.registerTool(
      'echo',
      description: 'echoes its message',
      inputSchema: ToolInputSchema(
        properties: {'message': JsonSchema.string()},
        required: ['message'],
      ),
      callback: (args, extra) {
        echoRuns++;
        lastArgs = args;
        return CallToolResult(
          content: [TextContent(text: 'echo: ${args['message']}')],
        );
      },
    );

    client = McpClient(Implementation(name: 'iron-live-client', version: '0.0.0'));
    final (clientT, serverT) = _PairTransport.linkedPair();
    await server.connect(serverT);
    await client.connect(clientT); // performs the initialize handshake
  }

  setUp(wire);
  tearDown(() async {
    await client.close();
    await server.close();
  });

  test('tools/list advertises the schema CLOSED over the real transport', () async {
    final listed = await client.listTools();
    final echo = listed.tools.firstWhere((t) => t.name == 'echo');
    final schema = echo.inputSchema.toJson();
    // The half of advertisement==runtime the client can SEE: the closed door.
    expect(schema['additionalProperties'], isFalse);
    expect((schema['properties'] as Map).keys, contains('message'));
  });

  test('a VALID tools/call runs the tool and returns its result', () async {
    final res = await client.callTool(
      const CallToolRequest(name: 'echo', arguments: {'message': 'hi'}),
    );
    expect(res.isError, isFalse);
    expect((res.content.first as TextContent).text, 'echo: hi');
    expect(echoRuns, 1); // the body actually ran
    expect(lastArgs?['message'], 'hi');
  });

  test('an UNDECLARED extra arg is REFUSED and the tool body never runs',
      () async {
    var refused = false;
    try {
      final res = await client.callTool(
        const CallToolRequest(
          name: 'echo',
          arguments: {'message': 'hi', 'sneaky': 'p@ssw0rd'},
        ),
      );
      // Modern-protocol path: the SDK returns an error RESULT rather than
      // throwing. It must be flagged an error and must not have run the body.
      refused = res.isError;
      final text = (res.content.first as TextContent).text;
      // Whatever the wording, the refusal must not leak the argument value.
      expect(text, isNot(contains('p@ssw0rd')));
    } on McpError catch (e) {
      // Legacy/initialization-protocol path: the SDK rejects the closed schema
      // with JSON-RPC invalidParams (-32602) — the exact code the iCE gate saw.
      refused = true;
      expect(e.code, ErrorCode.invalidParams.value);
      expect(e.code, -32602);
    }
    expect(refused, isTrue, reason: 'undeclared arg must be refused, not dropped');
    // The load-bearing proof: advertisement == runtime. The extra never reached
    // the tool. A silent-drop implementation would have run it with 1 arg.
    expect(echoRuns, 0);
    expect(lastArgs, isNull);
  });

  test('a valid call still works AFTER a refused one (server stays healthy)',
      () async {
    // Refuse one.
    try {
      await client.callTool(
        const CallToolRequest(
          name: 'echo',
          arguments: {'message': 'x', 'extra': 1},
        ),
      );
    } on McpError catch (_) {/* legacy path throws; fine */}
    // Then a clean call on the same live session must succeed normally.
    final res = await client.callTool(
      const CallToolRequest(name: 'echo', arguments: {'message': 'again'}),
    );
    expect(res.isError, isFalse);
    expect((res.content.first as TextContent).text, 'echo: again');
    expect(echoRuns, 1); // only the clean call ran the body
  });

  test('a required declared arg that is MISSING is also refused (not run)',
      () async {
    var refused = false;
    try {
      final res = await client.callTool(
        const CallToolRequest(name: 'echo', arguments: {}),
      );
      refused = res.isError;
    } on McpError catch (e) {
      refused = true;
      expect(e.code, ErrorCode.invalidParams.value);
    }
    expect(refused, isTrue);
    expect(echoRuns, 0); // schema enforcement kept the body from running
  });
}
