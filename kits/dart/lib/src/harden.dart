import 'package:mcp_dart/mcp_dart.dart';

import 'messages.dart';
import 'strict_args.dart';

/// The mcp_dart adapter. The two operations that make "advertisement == runtime"
/// true are pure statics ([stamp] advertises the schema closed; [refusalFor]
/// enforces it at call time), so both are unit-testable without a live transport.
/// [HardenedServer] just wires them into an [McpServer].
class Harden {
  Harden._();

  /// Advertise closed: a copy of [schema] with `additionalProperties: false`
  /// when it is enforceable (has `properties`, not opted open); otherwise
  /// [schema] unchanged (an opted-open or unintrospectable schema is never
  /// quietly closed). This is what `tools/list` will show.
  static ToolInputSchema? stamp(ToolInputSchema? schema) {
    if (schema == null) return null;
    final json = schema.toJson();
    final enforced =
        json.containsKey('properties') && json['additionalProperties'] != true;
    if (!enforced) return schema;
    return ToolInputSchema(
      properties: schema.properties,
      required: schema.required,
      additionalProperties: false,
    );
  }

  /// The refusal result for a call carrying an undeclared argument, or `null`
  /// when the call is clean (or the schema is unenforceable / opted open). The
  /// message names the offending keys and NEVER echoes an argument value; the
  /// structured payload mirrors the Python/TS/PHP kits so the shared corpus
  /// passes identically.
  static CallToolResult? refusalFor(
    String name,
    ToolInputSchema? schema,
    Map<String, dynamic>? args, {
    String reconnectHint = Messages.defaultReconnectHint,
  }) {
    final r = StrictArgs.check(
      schema?.toJson(),
      args,
      toolName: name,
      reconnectHint: reconnectHint,
    );
    if (r.ok) return null;
    return CallToolResult(
      content: [TextContent(text: r.message!)],
      isError: true,
      structuredContent: {
        'ironmcp': {
          'refused': true,
          'tool': name,
          'unknown': r.unknown,
          'accepted': r.accepted,
        },
      },
    );
  }
}

/// Wraps an mcp_dart [McpServer] so every tool registered through it is hardened:
/// its input schema is advertised closed and an undeclared argument is refused
/// at call time instead of silently dropped. Tool bodies are untouched. Pass
/// [inner] to your `StreamableMcpServer`/serve path; register tools on the
/// wrapper.
class HardenedServer {
  HardenedServer(this.inner, {this.reconnectHint = Messages.defaultReconnectHint});

  final McpServer inner;
  final String reconnectHint;

  RegisteredTool registerTool(
    String name, {
    String? title,
    String? description,
    ToolInputSchema? inputSchema,
    ToolOutputSchema? outputSchema,
    ToolAnnotations? annotations,
    Map<String, dynamic>? meta,
    required ToolFunction callback,
  }) {
    return inner.registerTool(
      name,
      title: title,
      description: description,
      inputSchema: Harden.stamp(inputSchema),
      outputSchema: outputSchema,
      annotations: annotations,
      meta: meta,
      callback: (args, extra) {
        final refusal =
            Harden.refusalFor(name, inputSchema, args, reconnectHint: reconnectHint);
        return refusal ?? callback(args, extra);
      },
    );
  }
}

/// Wrap [server] for hardened tool registration.
HardenedServer harden(McpServer server,
        {String reconnectHint = Messages.defaultReconnectHint}) =>
    HardenedServer(server, reconnectHint: reconnectHint);
