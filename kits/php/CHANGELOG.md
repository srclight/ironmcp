# Changelog

## 0.2.0 — 2026-09-01

The full ironmcp substrate, in parity with the Python, TypeScript, and Dart kits and
proven by the shared conformance corpus.

### Added
- **Self-discovery registry** — a server registers itself; agents enumerate every live
  ironmcp server. Registry file format byte-identical across all four language kits.
- **Structured readiness + health** — a readiness report with a verdict that excludes
  environmental blocks, plus a lightweight health tool.
- **Transport hardening** — a bearer-guarded endpoint, an open health check, and a
  DNS-rebinding host guard on by default (best-effort `Daemon::stop`).
- **Content + clean-quit helpers** — image/binary tool results with an empty-capture
  guard, and a fenced, ordered, idempotent shutdown scaffold.

## 0.1.1 and earlier

The pure core (Messages + StrictArgs, no SDK import), the `Harden` adapter over the
official `mcp/sdk`, and the conformance corpus runner. See tags `php-0.1.1`, `php-0.1.0`.
