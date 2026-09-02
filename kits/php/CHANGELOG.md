# Changelog

## 0.3.0 — 2026-09-02

### Changed (BREAKING) — readiness report shape
`ReadinessReport::toArray` now follows the ecosystem health-check convention plus a
map-by-id structure, identical across all four kits (proven byte-for-byte):
- top-level verdict `overall_status` → **`status`** (IETF health-check / Kubernetes /
  Spring Actuator vocabulary).
- `features`, `data_files`, `libs` → **objects keyed by id/name**, not lists (an empty map
  encodes as `{}`, not `[]`) — read `features["<id>"].status` in one hop; no duplicate id.
- `libs` → **`dependencies`**; the FFI symbol counts appear ONLY when a probe ran, so a
  service/database dependency carries just `{loaded, error?}`.
The five states and the verdict rule (excludes blocked/off) are unchanged. Spec:
[`spec/readiness.md`](../../spec/readiness.md).

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
