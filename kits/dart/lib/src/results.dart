import 'dart:convert';

import 'package:mcp_dart/mcp_dart.dart';

/// Content/result helpers — the generic PIPING an app tool rides on. The
/// screenshot/audio CAPTURE stays app-side; ironmcp owns how raw bytes become a
/// well-formed, guarded MCP result. No helper echoes a caller-supplied value.
class Results {
  Results._();

  static const JsonEncoder _enc = JsonEncoder.withIndent('  ');

  /// Success result carrying pretty-printed JSON.
  static CallToolResult json(Map<String, dynamic> data) =>
      CallToolResult(content: [TextContent(text: _enc.convert(data))]);

  /// Success result carrying plain text.
  static CallToolResult text(String message) =>
      CallToolResult(content: [TextContent(text: message)]);

  /// An error result (`isError: true`) so the caller/agent sees the tool failed.
  static CallToolResult error(String message) =>
      CallToolResult(content: [TextContent(text: message)], isError: true);

  /// Minimum bytes that count as real payload. A WSLg/X11 capture can exit 0 yet
  /// emit an empty (<=8-byte) file; treat that as a failure, not media (loqu8
  /// invariant #8).
  static const int minBytes = 8;

  /// Image result, or an [error] when the bytes are missing/too small.
  static CallToolResult image(List<int> bytes, {String mimeType = 'image/png'}) =>
      _binary(bytes, mimeType, kind: 'image');

  /// Audio result (iCE speaks), or an [error] when empty/too small. Proves the
  /// piping is not PNG-only.
  static CallToolResult audio(List<int> bytes, {String mimeType = 'audio/wav'}) =>
      _binary(bytes, mimeType, kind: 'audio');

  static CallToolResult _binary(List<int> bytes, String mimeType,
      {required String kind}) {
    if (bytes.length <= minBytes) {
      return error(
        'empty or truncated $kind (${bytes.length} bytes) — '
        'the capture produced no usable data',
      );
    }
    final data = base64Encode(bytes);
    return CallToolResult(content: [
      kind == 'image'
          ? ImageContent(data: data, mimeType: mimeType)
          : AudioContent(data: data, mimeType: mimeType),
    ]);
  }

  /// Truncate [body] to [maxChars], appending a marker naming how many chars were
  /// dropped, so an agent never mistakes a partial payload for the whole thing.
  static CallToolResult truncatedText(String body, {int maxChars = 20000}) {
    if (body.length <= maxChars) return text(body);
    final dropped = body.length - maxChars;
    return text('${body.substring(0, maxChars)}\n…[truncated $dropped chars]');
  }
}
