# conformance — ADVERTISEMENT == RUNTIME

## The invariant

The single property an ironmcp kit guarantees, and the one the corpus checks:

> **Whatever the catalog tells an agent about extra arguments, the runtime must actually
> do.**

It is deliberately NOT "additionalProperties is always false" — that would cement a
two-state world and fight a legitimate passthrough tool that opts out with
`additionalProperties: true`. ADVERTISEMENT == RUNTIME catches BOTH failures this class of
bug produces:

- **advertised-closed-but-runtime-open** — the original silent-discard (schema is silent
  or false, but extras are accepted).
- **advertised-open-but-runtime-refuses** — its reverse (schema stamped false, but the
  server accepts extras; or advertised true while the server refuses).

## The check (`assert_enforces`)

For each introspectable tool (object schema with `properties`):

- `additionalProperties: true` → skip (declared open; honoured, not a lie).
- `additionalProperties: false` → send one probe argument the tool does not declare; the
  call **must** come back as an error result. If it succeeds, the guarantee is not enforced.
- neither (the schema is **silent**) → **fail**: the catalog tells an agent extras are
  fine while the SDK would drop them.

A kit must also assert its check **fires** — i.e. rejects a bare, unguarded server. A
conformance check never watched to fail manufactures confidence and is worse than none.

## Driving the check

The check must exercise the server the way a real client does — through an actual request
path, not a helper that bypasses the server's request middleware. (In the reference kit,
`MCPServer.call_tool()` bypasses middleware; the check drives an in-memory
client↔server session instead.)

## The corpus

The prose above is executable as [`conformance/`](../conformance/README.md): JSON cases,
owned by no language, that every kit's runner reads and drives against its own server.
New behaviour enters ironmcp only with a case that pins it.
