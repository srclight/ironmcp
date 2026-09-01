import 'dart:async';

/// A fenced, idempotent, ORDERED shutdown scaffold. The steps are app-supplied —
/// an app releases what only it owns, flushes telemetry, stops its MCP server,
/// destroys its window, exits — and ironmcp guarantees they run **once, in
/// order, each fenced** so one failure cannot strand the rest. The ORDER is the
/// caller's contract (e.g. flush BEFORE stop, or the final telemetry batch is
/// lost — loqu8 invariant #5); the run-once guard is invariant #6.
class CleanQuit {
  CleanQuit(this.steps, {this.onError});

  final List<Future<void> Function()> steps;

  /// Called with `(index, error)` when a step throws; the sequence continues.
  final void Function(int index, Object error)? onError;

  bool _done = false;
  bool get hasRun => _done;

  /// Run the sequence once. A second call is a no-op (#6). Each step is fenced;
  /// a throwing step is reported via [onError] and does NOT abort the rest.
  Future<void> run() async {
    if (_done) return;
    _done = true;
    for (var i = 0; i < steps.length; i++) {
      try {
        await steps[i]();
      } catch (e) {
        // The error handler is itself fenced: a throwing onError must NOT abort
        // the remaining steps — otherwise one bad reporter strands the shutdown
        // sequence, the very failure this scaffold exists to prevent.
        try {
          onError?.call(i, e);
        } catch (_) {}
      }
    }
  }
}

/// Reply-before-quit: return [result] to the caller NOW, then run [quit] on a
/// later tick, so the HTTP response is written before the endpoint tears down
/// (loqu8 invariant #1 — quitting inside the handler drops the reply and reads
/// as a failed tool call). [delay] mirrors loqu8's ~300ms grace.
T replyThenQuit<T>(
  T result,
  Future<void> Function() quit, {
  Duration delay = const Duration(milliseconds: 300),
}) {
  Timer(delay, quit);
  return result;
}
