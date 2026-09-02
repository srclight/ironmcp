# Changelog

## 0.5.0 — 2026-09-02

### Changed (BREAKING) — readiness report shape
`ReadinessReport.toJSON` now follows the ecosystem health-check convention plus a
map-by-id structure, identical across all four kits (proven byte-for-byte):
- top-level verdict `overall_status` → **`status`** (IETF health-check / Kubernetes /
  Spring Actuator vocabulary).
- `features`, `data_files`, `libs` → **objects keyed by id/name**, not arrays — read
  `features["<id>"].status` in one hop; no array order to keep identical; no duplicate id.
- `libs` → **`dependencies`**; the FFI symbol counts appear ONLY when a probe ran, so a
  service/database dependency carries just `{loaded, error?}`.
The five states and the verdict rule (excludes blocked/off) are unchanged. Spec:
[`spec/readiness.md`](../../spec/readiness.md).

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
