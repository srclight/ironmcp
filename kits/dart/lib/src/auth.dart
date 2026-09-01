import 'dart:convert';

/// Constant-time bearer-token check. Fails CLOSED on an empty expected token,
/// and compares in constant time so a timing side channel cannot recover the
/// secret (never a fast `==` on a credential). The live HTTP wiring — rejecting
/// a request with 401 `WWW-Authenticate: Bearer` — is composed into the transport
/// in F8; this is the pure, testable core.
class BearerAuth {
  BearerAuth(this.expectedToken) {
    if (expectedToken.isEmpty) {
      throw ArgumentError('bearer token must not be empty — fail closed');
    }
  }

  final String expectedToken;

  /// True iff [authorizationHeader] is exactly `Bearer <expectedToken>`. A
  /// missing/empty/wrong header is rejected.
  bool accepts(String? authorizationHeader) {
    if (authorizationHeader == null) return false;
    const prefix = 'Bearer ';
    if (!authorizationHeader.startsWith(prefix)) return false;
    return _constantTimeEquals(
        authorizationHeader.substring(prefix.length), expectedToken);
  }

  static bool _constantTimeEquals(String a, String b) {
    final ab = utf8.encode(a);
    final bb = utf8.encode(b);
    var diff = ab.length ^ bb.length; // length mismatch -> non-zero
    final n = ab.length > bb.length ? ab.length : bb.length;
    for (var i = 0; i < n; i++) {
      final x = i < ab.length ? ab[i] : 0;
      final y = i < bb.length ? bb[i] : 0;
      diff |= x ^ y;
    }
    return diff == 0;
  }
}

/// DNS-rebinding / host-allowlist guard. Posture is ON by default: a request
/// whose `Host` header is not in [allowedHosts] is rejected. loqu8 bound
/// `0.0.0.0` with rebinding OFF while a comment falsely claimed it was on — this
/// defaults it ON (invariant #4). Give it the hosts the server legitimately
/// answers as (add the WSL/LAN name/IP + `localhost` when 0.0.0.0-bound, so WSL
/// reach still works while a rebinding attacker's `Host` is refused).
class HostGuard {
  HostGuard({required Iterable<String> allowedHosts, this.allowPortlessMatch = true})
      // HTTP Host is case-insensitive (RFC 7230 §2.7.3 / §5.4), so the allowlist
      // is folded to lower case once and every incoming host is folded before
      // comparison — 'Localhost' matches 'localhost'.
      : allowedHosts = allowedHosts.map((h) => h.toLowerCase()).toSet();

  final Set<String> allowedHosts;
  final bool allowPortlessMatch;

  /// True iff [hostHeader] is allowed. A null/empty host is rejected. Matching is
  /// case-insensitive per RFC 7230.
  bool accepts(String? hostHeader) {
    if (hostHeader == null || hostHeader.isEmpty) return false;
    final host = hostHeader.toLowerCase();
    if (allowedHosts.contains(host)) return true;
    if (allowPortlessMatch && allowedHosts.contains(host.split(':').first)) {
      return true;
    }
    return false;
  }
}
