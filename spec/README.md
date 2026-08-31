# ironmcp specification

The behavioural contract every ironmcp kit implements, stated independent of any
language. A kit conforms when a server built with its strict layer passes the
[conformance corpus](../conformance/README.md); the corpus is the executable form of
this prose, and each rule below names the case that pins it.

- **[strict-args.md](strict-args.md)** — refusing unknown tool arguments.
- **[conformance.md](conformance.md)** — the ADVERTISEMENT == RUNTIME invariant.

## Positioning

Dedicated, hardened, conformant MCP tooling on every platform — so nobody hand-rolls
JSON-RPC again. Where an official SDK exists, ironmcp is the hardening + conformance
layer on top of it; where none does, ironmcp is the dedicated toolkit itself. One
corpus unifies both: layer-on-SDK or provide-your-own, every kit passes the same tests.

## Versioning

The spec, the corpus, and every language kit share one version (lockstep). "ironmcp X.Y
behaves identically in all languages" is only meaningful if the versions match.
