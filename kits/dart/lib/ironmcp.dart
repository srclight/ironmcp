/// ironmcp — hardened, conformant MCP tools for Dart / Flutter.
///
/// The pure core (no SDK import): the strict-args rule and the bounded refusal
/// message, shared with the Python, TypeScript, and PHP kits and proven by the
/// same language-neutral conformance corpus. The mcp_dart adapter (`harden`)
/// wires this into a live server; it lives behind a separate import so the core
/// stays SDK-free and trivially testable.
library;

export 'src/messages.dart';
export 'src/strict_args.dart';
export 'src/harden.dart';
export 'src/results.dart';
