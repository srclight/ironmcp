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

    // GAP (canonical fix #1): HTTP Host is case-insensitive (RFC 7230), so a
    // differently-cased host that names an allowed origin MUST be accepted.
    test('matches case-insensitively (Localhost == localhost)', () {
      expect(guard.accepts('Localhost'), isTrue);
      expect(guard.accepts('LOCALHOST:8080'), isTrue);
      expect(guard.accepts('Wasabi.Local:18888'), isTrue);
    });

    test('an allowlist entry given in mixed case still matches a lowercase host',
        () {
      final g = HostGuard(allowedHosts: ['MyHost.Local', '127.0.0.1']);
      expect(g.accepts('myhost.local'), isTrue);
      expect(g.accepts('MYHOST.LOCAL:9000'), isTrue);
    });

    // GAP: the non-default allowPortlessMatch:false branch — strict host:port
    // matching — was never exercised.
    test('allowPortlessMatch:false requires an exact host[:port] match', () {
      final strict = HostGuard(
        allowedHosts: ['localhost:8888', '127.0.0.1:8888'],
        allowPortlessMatch: false,
      );
      expect(strict.accepts('localhost:8888'), isTrue);
      expect(strict.accepts('LOCALHOST:8888'), isTrue); // still case-insensitive
      // A bare host (no port) does NOT match a host:port allowlist entry now.
      expect(strict.accepts('localhost'), isFalse);
      expect(strict.accepts('localhost:9999'), isFalse); // wrong port
    });

    test('allowPortlessMatch:false still accepts a portless entry matched exactly',
        () {
      final strict =
          HostGuard(allowedHosts: ['localhost'], allowPortlessMatch: false);
      expect(strict.accepts('localhost'), isTrue);
      expect(strict.accepts('localhost:8888'), isFalse); // port not stripped
    });
  });
}
