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

  // GAP (canonical fix #6): pin the EXACT byte boundary of invariant #8. minBytes
  // is 8 and the guard is `<= minBytes`, so 8 bytes must be REJECTED and 9 bytes
  // ACCEPTED — the off-by-one that decides whether an empty capture reads as media.
  test('image byte-guard boundary: exactly 8 bytes is REJECTED', () {
    final r = Results.image(List<int>.filled(8, 1));
    expect(r.isError, isTrue);
    expect((r.content.first as TextContent).text, contains('(8 bytes)'));
  });

  test('image byte-guard boundary: exactly 9 bytes is ACCEPTED as media', () {
    final bytes = List<int>.generate(9, (i) => i);
    final r = Results.image(bytes);
    expect(r.isError, isFalse);
    expect(base64Decode((r.content.first as ImageContent).data), bytes);
  });

  test('audio byte-guard boundary: 8 rejected, 9 accepted (same guard)', () {
    expect(Results.audio(List<int>.filled(8, 7)).isError, isTrue);
    final bytes = List<int>.generate(9, (i) => 200 + i);
    final r = Results.audio(bytes);
    expect(r.isError, isFalse);
    expect(base64Decode((r.content.first as AudioContent).data), bytes);
  });

  // GAP: Results.text() had no direct test.
  test('text() carries plain text as a success result', () {
    final r = Results.text('hello');
    expect(r.isError, isFalse);
    expect((r.content.first as TextContent).text, 'hello');
  });

  // GAP: truncatedText boundary at body.length == maxChars — the guard is
  // `<= maxChars`, so text of exactly maxChars is NOT truncated (no marker).
  test('truncatedText leaves text of exactly maxChars intact (boundary)', () {
    final exact = 'x' * 10;
    final t = (Results.truncatedText(exact, maxChars: 10).content.first as TextContent).text;
    expect(t, exact);
    expect(t, isNot(contains('truncated')));
  });

  test('truncatedText truncates at exactly maxChars + 1 (boundary)', () {
    final overBy1 = 'x' * 11;
    final t = (Results.truncatedText(overBy1, maxChars: 10).content.first as TextContent).text;
    expect(t, contains('[truncated 1 chars]'));
    expect(t, startsWith('x' * 10));
  });
}
