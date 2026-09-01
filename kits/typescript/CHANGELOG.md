# Changelog

## 0.4.0 — 2026-09-01

The full ironmcp substrate, in parity with the Python, PHP, and Dart kits and proven by
the shared conformance corpus.

### Added
- **Self-discovery registry** — a server registers itself; agents enumerate every live
  ironmcp server. Registry file format byte-identical across all four language kits.
- **Structured readiness + health** — a readiness report with a verdict that excludes
  environmental blocks, plus a lightweight health tool.
- **Transport hardening** — a bearer-guarded endpoint, an open health check naming
  capabilities, and a DNS-rebinding host guard on by default (RFC 7230 case-insensitive,
  IPv6-bracket aware).
- **Content + clean-quit helpers** — image/binary tool results with an empty-capture
  guard, and a fenced, ordered, idempotent shutdown scaffold.

## 0.3.1 and earlier

The strict-args guard (`strictServer` / `guardServer`) and the conformance runner. See
the git history and release tags (`ts-0.3.1`, `ts-0.3.0`, …) for details.
