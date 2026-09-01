# ironmcp (Dart / Flutter)

Hardened, conformant MCP tools for Dart and Flutter. Tools **refuse** an undeclared
argument instead of silently dropping it, and advertise exactly what they enforce
(`additionalProperties: false` — advertisement == runtime). This is the Dart kit of
[ironmcp](https://github.com/srclight/ironmcp), the hardening-and-conformance standard
for MCP servers: one spec, one language-neutral conformance corpus, a native kit per
language (Python, TypeScript, PHP, Dart).

## Why it matters for a tool a model will call

Most MCP SDKs silently drop any argument the caller did not declare and run the tool
anyway. For a human that is an annoyance; for an AI agent it is a trap — mistype
`query` as `querry`, or invent a parameter that sounds right, and the tool returns a
confident answer to a question you did not ask, with nothing signalling the input was
wrong. ironmcp turns that into a bounded, machine-readable **refusal** that names the
offending argument, lists what the tool accepts, and says nothing ran — so the caller
self-corrects on its next turn.

## Install

```console
dart pub add ironmcp
```

ironmcp is a layer over [`mcp_dart`](https://pub.dev/packages/mcp_dart) — it works with
the server you already build.

## Harden a server in one line

Change one constructor. Every tool the server registers is then hardened; no tool
bodies change.

```dart
import 'package:ironmcp/ironmcp.dart' show StrictMcpServer;

final server = StrictMcpServer(
  Implementation(name: 'search', version: '1.0.0'),
  options: options,
);
// every server.registerTool(...) below is now hardened — no call-site changes
```

`StrictMcpServer` is a drop-in subclass of `mcp_dart`'s `McpServer`, so an existing
server hardens by changing its constructor and nothing else. See
[`example/`](example/ironmcp_example.dart) for a complete runnable server.

Prefer composition? `harden(innerServer)` wraps a server you already hold, and
`Harden.stamp` / `Harden.refusalFor` are pure statics for building your own adapter.

## More than the guard — the substrate

From this one dependency you also get, matching the other language kits:

- **Self-discovery registry** — your server registers itself; any agent can enumerate
  every live ironmcp server (namespace, port, capabilities) from one shared file whose
  format is byte-identical across all four languages.
- **Structured readiness + health** — a full readiness report (which features are ready,
  degraded, or failed) and a lightweight health check, so a caller can tell whether a
  server is ready before calling it.
- **Hardened serving** — a bearer-guarded endpoint, an open health check, and a
  DNS-rebinding host guard on by default.
- **Content + clean-quit helpers** — correct image/binary tool results (with an
  empty-capture guard) and an honest `quit` tool an agent can call.

## The refusal is built for an agent, not a human

Every refusal carries `structuredContent.ironmcp = {refused, tool, unknown[], accepted[]}`
alongside the prose, so a caller parses which arguments were rejected instead of scraping
message text. The message names the offending keys but never echoes their values (a value
could be a secret or a megabyte) and caps the list so it cannot become an amplifier.

## Proven in production

ironmcp hardens a desktop application's live MCP server (60+ tools) on both Linux and
Windows, with zero behaviour change — a mistyped argument that used to return a confident
wrong answer now returns a clear refusal. The guarantee it enforces is the one
[OWASP's MCP Security guidance](https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html)
recommends.

## License

MIT — see [LICENSE](LICENSE).
