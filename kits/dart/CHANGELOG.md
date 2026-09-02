# Changelog

## 0.2.0 — 2026-09-02

### Changed (BREAKING) — readiness report shape
`ReadinessReport.toJson` now follows the ecosystem health-check convention plus a
map-by-id structure, identical across all four kits (proven byte-for-byte):
- top-level verdict `overall_status` → **`status`** (IETF health-check / Kubernetes /
  Spring Actuator vocabulary).
- `features`, `data_files`, `libs` → **objects keyed by id/name**, not lists — read
  `features["<id>"].status` in one hop; no list order to keep identical; no duplicate id.
- `libs` → **`dependencies`**; the FFI symbol counts appear ONLY when a probe ran, so a
  service/database dependency carries just `{loaded, error?}`.
The five states and the verdict rule (excludes blocked/off) are unchanged. Spec:
[`spec/readiness.md`](../../spec/readiness.md).

## 0.1.0 — 2026-09-01

First published release of the Dart / Flutter kit. Implements the full ironmcp
substrate, proven by the shared language-neutral conformance corpus.

### Added
- **Strict-args guard** — `StrictMcpServer`, a drop-in subclass of `mcp_dart`'s
  `McpServer`: every registered tool advertises its schema closed
  (`additionalProperties: false`) and refuses undeclared arguments with a bounded,
  machine-readable refusal (`structuredContent.ironmcp = {refused, tool, unknown, accepted}`).
  Composition alternatives `harden()` / `HardenedServer` and the pure statics
  `Harden.stamp` / `Harden.refusalFor`.
- **Self-discovery registry** — a server registers itself; agents enumerate every live
  ironmcp server. Registry file format byte-identical across the Python, TypeScript,
  PHP, and Dart kits.
- **Structured readiness + health** — a readiness report with a verdict that excludes
  environmental blocks, plus a lightweight health check.
- **Transport hardening** — constant-time bearer auth and a DNS-rebinding host guard
  (on by default, RFC 7230 case-insensitive, IPv6-bracket aware).
- **Content + clean-quit helpers** — image/binary tool results with an empty-capture
  guard, and a fenced, ordered, idempotent shutdown scaffold.
