import 'messages.dart';

/// The outcome of a strict-args check: either accepted, or a refusal carrying
/// the offending keys and the ready-made message.
class StrictResult {
  const StrictResult.ok()
      : ok = true,
        unknown = const [],
        accepted = const [],
        message = null;

  const StrictResult.refused({
    required this.unknown,
    required this.accepted,
    required this.message,
  }) : ok = false;

  final bool ok;
  final List<String> unknown;
  final List<String> accepted;
  final String? message;
}

/// The 3-state rule + the advertise stamp. No SDK import; pure. The schema is
/// authoritative, and a guard that bricks what it cannot read is worse than the
/// bug it prevents — so it enforces ONLY when the schema is introspectable and
/// not explicitly opted open.
///
/// - State 1 (unintrospectable: no `properties`)  -> permissive.
/// - State 2 (has `properties`, not opted open)    -> enforce; refuse unknowns.
/// - State 3 (`additionalProperties: true`)        -> permissive (opted out).
class StrictArgs {
  StrictArgs._();

  static StrictResult check(
    Map<String, Object?>? schema,
    Map<String, Object?>? args, {
    String toolName = 'tool',
    String reconnectHint = Messages.defaultReconnectHint,
  }) {
    if (!_isEnforced(schema)) {
      return const StrictResult.ok(); // states 1 & 3
    }
    final props = schema!['properties'];
    final accepted = props is Map
        ? props.keys.map((k) => k.toString()).toList()
        : <String>[];
    final acceptedSet = accepted.toSet();
    final unknown = (args ?? const <String, Object?>{})
        .keys
        .map((k) => k.toString())
        .where((k) => !acceptedSet.contains(k))
        .toList()
      ..sort();
    if (unknown.isEmpty) return const StrictResult.ok();

    return StrictResult.refused(
      unknown: unknown,
      accepted: accepted,
      message: Messages.unknownArgs(
        toolName,
        unknown,
        accepted,
        reconnectHint: reconnectHint,
      ),
    );
  }

  /// Return a copy of [schema] with `additionalProperties: false` when it is
  /// enforced (state 2); otherwise return [schema] unchanged (same reference),
  /// so an opted-open or unintrospectable schema is never quietly closed.
  static Map<String, Object?>? stampClosed(Map<String, Object?>? schema) {
    if (!_isEnforced(schema)) return schema;
    return {...schema!, 'additionalProperties': false};
  }

  /// True only in state 2: `properties` present (even empty) and not opted open.
  static bool _isEnforced(Map<String, Object?>? schema) {
    return schema != null &&
        schema.containsKey('properties') &&
        schema['additionalProperties'] != true;
  }
}
