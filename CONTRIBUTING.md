# Contributing to ironmcp

ironmcp is one contract ([`spec/`](spec/)), one corpus ([`conformance/`](conformance/)), and a
native kit per language. Contributions that keep those three in agreement are welcome:
fixes to a kit, new conformance cases that pin a real behaviour, and new language kits.

## Run the tests

- **Python** (`kits/python/`): `python -m venv .venv && .venv/bin/pip install -e ".[dev]" && .venv/bin/python -m pytest -q`
- **TypeScript** (`kits/typescript/`): `npm install && npx vitest run && npm run build`

Both suites include the conformance corpus AND a proof that a bare, unguarded server FAILS it —
a corpus never watched to fail proves nothing. Keep both green.

## Change what ironmcp promises: the corpus comes first

New behaviour enters ironmcp only with a case in [`conformance/cases/`](conformance/cases/) that
pins it. Add or change the case first (see [`conformance/README.md`](conformance/README.md) for
the format), then make every kit pass it. A guarantee with no case is not a guarantee.

## Add a language kit

The two shipped kits ([`kits/python/`](kits/python/), [`kits/typescript/`](kits/typescript/))
are the worked examples. A new kit is four parts:

1. **The pure core** — implement the 3-state rule from [`spec/strict-args.md`](spec/strict-args.md)
   (no `properties` → permissive; `properties` present and not opted open → refuse unknown keys;
   `additionalProperties: true` → honour the opt-out) and the refusal message (name the keys,
   never echo values, cap the enumeration, diagnose NFKC-confusable names, end with a
   reconnect hint). This part imports no MCP SDK — it is testable on its own.
2. **The thin adapter(s)** — wrap your language's MCP SDK at the tool-call seam so an unknown
   argument is refused before the handler runs, and stamp `additionalProperties: false` onto
   the advertised schema **at the wire** (the serialized `tools/list` output, not a pre-
   serialization shape — some SDKs drop it otherwise). Support both the high-level and
   low-level server styles the SDK offers.
3. **The corpus runner** — read [`conformance/cases/`](conformance/cases/) and drive each case
   through a real in-memory client↔server session (every SDK ships an in-memory transport pair).
   Provide an `assert_enforces`-style entry point that throws on any failure.
4. **The proof** — a test that the strict server passes every case AND that a bare server FAILS
   the corpus. Then, optionally, the deployment glue (`serve_http`): a bearer-guarded `/mcp`, an
   open `/healthz` naming a capability, fail-closed on an empty token, with the session-manager
   lifespan handled so the port actually answers.

Keep runtime dependencies minimal (the guard is small and the supply chain is a write path into
every server that adopts it), and version the kit independently — the corpus, not a shared
version number, is the lockstep.

## Commits and releases

Small, focused commits. Kits release independently via git-flow (per-kit tags). Do not publish
to a registry without the maintainer's sign-off.
