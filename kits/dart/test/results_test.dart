import 'dart:convert';

import 'package:ironmcp/ironmcp.dart';
import 'package:mcp_dart/mcp_dart.dart';
import 'package:test/test.dart';

void main() {
  test('json wraps a map as pretty JSON success text', () {
    final r = Results.json({'a': 1});
    expect(r.isError, isFalse);
    expect((r.content.first as TextContent).text, contains('"a": 1'));
  });

  test('error sets isError:true', () {
    final r = Results.error('nope');
    expect(r.isError, isTrue);
    expect((r.content.first as TextContent).text, 'nope');
  });

  test('image REJECTS <=8 bytes (WSLg empty-capture trap, invariant #8)', () {
    final r = Results.image([1, 2, 3]);
    expect(r.isError, isTrue);
    expect((r.content.first as TextContent).text, contains('empty or truncated image'));
  });

  test('image base64-encodes real bytes byte-safely (round-trips exactly)', () {
    final bytes = List<int>.generate(64, (i) => i);
    final r = Results.image(bytes, mimeType: 'image/png');
    expect(r.isError, isFalse);
    final img = r.content.first as ImageContent;
    expect(img.mimeType, 'image/png');
    expect(base64Decode(img.data), bytes);
  });

  test('audio covers non-PNG binary (iCE speaks) and round-trips', () {
    final bytes = List<int>.generate(32, (i) => 255 - i);
    final r = Results.audio(bytes, mimeType: 'audio/wav');
    expect(r.isError, isFalse);
    final a = r.content.first as AudioContent;
    expect(a.mimeType, 'audio/wav');
    expect(base64Decode(a.data), bytes);
  });

  test('audio also guards the empty capture', () {
    expect(Results.audio(<int>[]).isError, isTrue);
  });

  test('truncatedText marks how many chars were dropped', () {
    final long = 'x' * 100;
    final t = (Results.truncatedText(long, maxChars: 10).content.first as TextContent).text;
    expect(t, contains('[truncated 90 chars]'));
    expect(t.length, lessThan(long.length));
  });

  test('truncatedText leaves short text intact', () {
    expect((Results.truncatedText('hi', maxChars: 10).content.first as TextContent).text, 'hi');
  });
}
