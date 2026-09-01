/// The pure refusal message. No SDK import. Bounded (caps the listed keys) and
/// never echoes an argument's VALUE — only names the offending keys — so a
/// hostile or huge payload cannot turn the guard into an amplifier or a leak.
///
/// Identical in intent to the Python, TypeScript, and PHP kits, so the shared
/// conformance corpus passes the same way in every language.
class Messages {
  Messages._();

  /// The one caneslight-style hint, supplied as data (not re-forked per method):
  /// an unknown-argument refusal from a server that predates the field usually
  /// means the running server is stale — reconnect the MCP rather than retrying.
  static const String defaultReconnectHint =
      'If you did not expect this, the server may be running older code than the '
      'client — reconnect the MCP and retry.';

  static const int _cap = 10;

  static String _capped(List<String> xs) {
    if (xs.length <= _cap) return xs.join(', ');
    final shown = xs.take(_cap).join(', ');
    return '$shown, … (${xs.length - _cap} more)';
  }

  /// Build the bounded refusal prose: names the unknown key(s), lists what the
  /// tool accepts, states nothing ran, and appends the reconnect hint.
  static String unknownArgs(
    String toolName,
    List<String> unknown,
    List<String> accepted, {
    String reconnectHint = defaultReconnectHint,
  }) {
    final acceptedPart = accepted.isEmpty
        ? "Tool '$toolName' accepts no arguments."
        : "Tool '$toolName' accepts: ${_capped(accepted)}.";
    return 'unknown argument(s): ${_capped(unknown)}. '
        '$acceptedPart Nothing was executed. $reconnectHint';
  }
}
