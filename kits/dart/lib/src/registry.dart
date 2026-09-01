import 'dart:convert';
import 'dart:io';

/// The CANONICAL registry `started_at` timestamp: ISO-8601 UTC, MILLISECOND
/// precision (exactly 3 fractional digits), trailing `Z` — e.g.
/// `2026-09-01T10:35:34.123Z`.
///
/// This is the ONE format every ironmcp kit MUST emit so `registry.json` stays
/// byte-identical across languages; it is exactly what JavaScript's
/// `Date.toISOString()` and Python's normalised `_now_iso()` produce. Dart's own
/// `DateTime.toIso8601String()` is the outlier — it emits variable 3-or-6-digit
/// precision (6 digits whenever the microsecond component is non-zero) — so it is
/// normalised here rather than used directly. Sub-millisecond microseconds are
/// TRUNCATED (floored), never rounded, matching Python's `microsecond // 1000`.
String isoMillisUtc(DateTime dt) {
  final u = dt.toUtc();
  String pad(int n, int width) => n.toString().padLeft(width, '0');
  return '${pad(u.year, 4)}-${pad(u.month, 2)}-${pad(u.day, 2)}'
      'T${pad(u.hour, 2)}:${pad(u.minute, 2)}:${pad(u.second, 2)}'
      '.${pad(u.millisecond, 3)}Z';
}

/// A live ironmcp server's registration. Language-neutral JSON (snake_case), so a
/// Dart iCE, a Python `*light` server, and a Node scarlight all read and write
/// the SAME discovery fabric. Deliberately carries no hand-kept tool list — a
/// consumer enumerates a server's tools via `tools/list` on its port (loqu8
/// invariant #3: the list that drifted from 6 to 66).
class IronMcpEntry {
  IronMcpEntry({
    required this.id,
    required this.namespace,
    required this.pid,
    this.host,
    this.port,
    this.transport,
    this.version,
    this.codeSha,
    Map<String, dynamic>? capabilities,
    DateTime? startedAt,
  })  : capabilities = capabilities ?? const {},
        startedAt = startedAt ?? DateTime.now().toUtc();

  final String id;
  final String namespace;
  final int pid;
  final String? host;
  final int? port;
  final String? transport;
  final String? version;
  final String? codeSha;
  final Map<String, dynamic> capabilities;
  final DateTime startedAt;

  Map<String, dynamic> toJson() => {
        'id': id,
        'namespace': namespace,
        'pid': pid,
        if (host != null) 'host': host,
        if (port != null) 'port': port,
        if (transport != null) 'transport': transport,
        if (version != null) 'version': version,
        if (codeSha != null) 'code_sha': codeSha,
        'capabilities': capabilities,
        'started_at': isoMillisUtc(startedAt),
      };

  static IronMcpEntry fromJson(Map<String, dynamic> j) => IronMcpEntry(
        id: j['id'] as String,
        namespace: j['namespace'] as String,
        pid: j['pid'] as int,
        host: j['host'] as String?,
        port: j['port'] as int?,
        transport: j['transport'] as String?,
        version: j['version'] as String?,
        codeSha: j['code_sha'] as String?,
        capabilities: (j['capabilities'] as Map?)?.cast<String, dynamic>(),
        startedAt: DateTime.tryParse((j['started_at'] as String?) ?? '')?.toUtc(),
      );
}

/// Self-discovery of ironmcp servers. File-backed, with a cross-process O_EXCL
/// lock around every read-modify-write (closes the lost-update TOCTOU, invariant
/// #9), pid-liveness pruning on read (lazy GC, invariant #10), and an XDG path
/// (not `~/.loqu8`). `namespace` keeps it estate-wide rather than Loqu8-only.
class IronMcpRegistry {
  IronMcpRegistry({
    Directory? dir,
    bool Function(int pid)? isPidAlive,
    this.lockTimeout = const Duration(seconds: 3),
    this.staleLockAfter = const Duration(seconds: 30),
  })  : _dir = dir ?? _defaultDir(),
        _isPidAlive = isPidAlive ?? _pidAliveDefault;

  final Directory _dir;
  final bool Function(int pid) _isPidAlive;
  final Duration lockTimeout;
  final Duration staleLockAfter;

  File get _file => File('${_dir.path}/registry.json');
  File get _lockFile => File('${_dir.path}/registry.json.lock');

  static Directory _defaultDir() {
    final env = Platform.environment;
    final base = env['XDG_RUNTIME_DIR'] ??
        env['XDG_STATE_HOME'] ??
        '${env['HOME'] ?? '.'}/.local/state';
    return Directory('$base/ironmcp');
  }

  static bool _pidAliveDefault(int p) {
    if (Platform.isLinux) return Directory('/proc/$p').existsSync();
    try {
      if (Platform.isWindows) {
        final r = Process.runSync('tasklist', ['/FI', 'PID eq $p']);
        return r.stdout.toString().contains('$p');
      }
      return Process.runSync('kill', ['-0', '$p']).exitCode == 0;
    } catch (_) {
      return true; // fail open — never prune a live entry we cannot verify
    }
  }

  Future<void> register(IronMcpEntry entry) => _withLock(() async {
        final map = await _read();
        map[entry.id] = entry.toJson();
        await _write(map);
      });

  Future<void> unregister(String id) => _withLock(() async {
        final map = await _read();
        map.remove(id);
        await _write(map);
      });

  /// Live servers, pruning any whose pid is dead (and rewriting the file if it
  /// pruned). A hard-killed process is cleaned up lazily on the next reader's
  /// scan, since its own `unregister` never ran (invariant #10).
  Future<List<IronMcpEntry>> discover() async {
    final live = <IronMcpEntry>[];
    await _withLock(() async {
      final map = await _read();
      var pruned = false;
      for (final key in map.keys.toList()) {
        final e = IronMcpEntry.fromJson((map[key] as Map).cast<String, dynamic>());
        if (_isPidAlive(e.pid)) {
          live.add(e);
        } else {
          map.remove(key);
          pruned = true;
        }
      }
      if (pruned) await _write(map);
    });
    return live;
  }

  Future<Map<String, dynamic>> _read() async {
    try {
      if (!await _file.exists()) return {};
      final txt = await _file.readAsString();
      if (txt.trim().isEmpty) return {};
      return (jsonDecode(txt) as Map).cast<String, dynamic>();
    } catch (_) {
      return {}; // corrupt/unreadable: start fresh rather than crash
    }
  }

  Future<void> _write(Map<String, dynamic> map) async {
    await _dir.create(recursive: true);
    final tmp = File(
        '${_file.path}.tmp.$pid.${DateTime.now().microsecondsSinceEpoch}');
    await tmp.writeAsString(const JsonEncoder.withIndent('  ').convert(map));
    await tmp.rename(_file.path); // atomic on the same filesystem
  }

  Future<void> _withLock(Future<void> Function() body) async {
    await _dir.create(recursive: true);
    final deadline = DateTime.now().add(lockTimeout);
    var acquired = false;
    while (true) {
      try {
        await _lockFile.create(exclusive: true);
        acquired = true;
        break;
      } on FileSystemException {
        // A crashed holder can leave a stale lock — steal it past staleLockAfter.
        try {
          final age = DateTime.now().difference(await _lockFile.lastModified());
          if (age > staleLockAfter) {
            await _lockFile.delete();
            continue;
          }
        } catch (_) {}
        if (DateTime.now().isAfter(deadline)) break; // proceed best-effort
        await Future<void>.delayed(const Duration(milliseconds: 5));
      }
    }
    try {
      await body();
    } finally {
      if (acquired) {
        try {
          await _lockFile.delete();
        } catch (_) {}
      }
    }
  }
}
