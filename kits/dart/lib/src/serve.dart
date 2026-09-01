import 'dart:async';
import 'dart:io';

/// Lifecycle wrapper for an MCP transport. Binds with a Windows-TIME_WAIT-aware
/// retry, keeps a failed start non-fatal (records [lastError] instead of
/// throwing), and stops cleanly. The bind/unbind are injected, so the retry
/// logic is unit-testable without opening a real port — and a caller wires the
/// real `StreamableMcpServer.start`/`.stop` in.
class IronMcpDaemon {
  IronMcpDaemon({
    required Future<void> Function() bind,
    Future<void> Function()? unbind,
    this.maxRetries = 3,
    this.retryDelay = const Duration(seconds: 2),
    this.onLog,
  })  : _bind = bind,
        _unbind = unbind;

  final Future<void> Function() _bind;
  final Future<void> Function()? _unbind;

  /// Bind attempts before giving up (loqu8 used 3).
  final int maxRetries;

  /// Delay between attempts (loqu8 used 2s — Windows TIME_WAIT).
  final Duration retryDelay;

  final void Function(String message)? onLog;

  bool _running = false;
  bool get isRunning => _running;

  Object? _lastError;

  /// The error from the last failed [start], or `null` if the last start
  /// succeeded (or start was never called).
  Object? get lastError => _lastError;

  /// Start, retrying up to [maxRetries] on [SocketException] — the Windows
  /// TIME_WAIT case where a prior process still holds the port (loqu8 invariant
  /// #2). Non-fatal: on final failure it records [lastError] and returns `false`
  /// rather than throwing, so a server that cannot bind does not crash the app.
  /// A non-socket error fails fast (no retry) and is likewise non-fatal.
  Future<bool> start() async {
    _lastError = null;
    for (var attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        await _bind();
        _running = true;
        return true;
      } on SocketException catch (e) {
        _lastError = e;
        if (attempt < maxRetries) {
          onLog?.call('bind busy (attempt $attempt/$maxRetries): $e — '
              'retrying in ${retryDelay.inSeconds}s');
          await Future<void>.delayed(retryDelay);
        }
      } catch (e) {
        _lastError = e;
        return false; // non-socket: do not retry, do not throw
      }
    }
    return false; // retries exhausted
  }

  /// Stop the transport (best-effort) and clear [isRunning]. Safe to call when
  /// not running.
  Future<void> stop() async {
    try {
      await _unbind?.call();
    } finally {
      _running = false;
    }
  }
}
