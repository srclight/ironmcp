import 'package:ironmcp/ironmcp.dart';
import 'package:mcp_dart/mcp_dart.dart';

/// A one-line-hardened MCP server.
///
/// The only change from a plain `mcp_dart` server is the constructor:
/// `McpServer(...)` becomes `StrictMcpServer(...)`. Every tool registered
/// below then advertises its input schema CLOSED (`additionalProperties: false`)
/// and enforces it — a call carrying an argument the tool never declared is
/// REFUSED with a bounded, machine-readable error, instead of being run with
/// that argument silently dropped. Advertisement == runtime.
Future<void> main() async {
  final server = StrictMcpServer(
    Implementation(name: 'search', version: '1.0.0'),
    options: McpServerOptions(
      capabilities: ServerCapabilities(tools: ServerCapabilitiesTools()),
    ),
  );

  server.registerTool(
    'search',
    description: 'Search the corpus for a query.',
    inputSchema: ToolInputSchema(
      properties: {'query': JsonSchema.string()},
      required: ['query'],
    ),
    callback: (args, extra) {
      // Reached ONLY for a well-formed call. A call such as
      // {"querry": "hi"} (a typo) or {"query": "hi", "limit": 5} (an invented
      // argument) never arrives here — the client receives an ironmcp refusal
      // naming the unknown key and what the tool actually accepts, and nothing
      // ran. An AI agent reads that and fixes its next call.
      final query = args['query'] as String;
      return CallToolResult(content: [TextContent(text: 'results for: $query')]);
    },
  );

  // Serve over stdio: an MCP client launches this process and speaks to it.
  await server.connect(StdioServerTransport());
}
