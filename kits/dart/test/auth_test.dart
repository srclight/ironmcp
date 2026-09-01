import 'package:ironmcp/ironmcp.dart';
import 'package:test/test.dart';

void main() {
  group('BearerAuth', () {
    final auth = BearerAuth('s3cret-token');

    test('accepts the exact Bearer token', () {
      expect(auth.accepts('Bearer s3cret-token'), isTrue);
    });
    test('rejects a wrong token', () {
      expect(auth.accepts('Bearer nope'), isFalse);
    });
    test('rejects a missing/empty/malformed header', () {
      expect(auth.accepts(null), isFalse);
      expect(auth.accepts(''), isFalse);
      expect(auth.accepts('s3cret-token'), isFalse); // no Bearer prefix
      expect(auth.accepts('Bearer '), isFalse); // empty presented token
    });
    test('an empty expected token is refused at construction (fail closed)', () {
      expect(() => BearerAuth(''), throwsArgumentError);
    });
    test('a token that is a prefix of the secret is rejected (constant-time)', () {
      expect(auth.accepts('Bearer s3cret'), isFalse);
    });
  });

  group('HostGuard (DNS-rebinding, default ON — invariant #4)', () {
    final guard = HostGuard(allowedHosts: ['localhost', '127.0.0.1', 'wasabi.local']);

    test('accepts an allowed host, with or without a port', () {
      expect(guard.accepts('localhost'), isTrue);
      expect(guard.accepts('localhost:8080'), isTrue);
      expect(guard.accepts('wasabi.local:18888'), isTrue);
    });
    test('rejects a rebinding attacker host and a null/empty host', () {
      expect(guard.accepts('evil.example.com'), isFalse);
      expect(guard.accepts('evil.example.com:8080'), isFalse);
      expect(guard.accepts(null), isFalse);
      expect(guard.accepts(''), isFalse);
    });
  });
}
