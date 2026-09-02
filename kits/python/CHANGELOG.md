# Changelog

## 0.7.0 — 2026-09-02

### Changed (BREAKING) — readiness report shape
`ReadinessReport.to_json` now follows the ecosystem health-check convention plus a
map-by-id structure, identical across all four kits (proven byte-for-byte):
- top-level verdict `overall_status` → **`status`** (IETF health-check / Kubernetes /
  Spring Actuator vocabulary).
- `features`, `data_files`, `libs` → **objects keyed by id/name**, not lists — read
  `features["<id>"]["status"]` in one hop; no list order to keep identical; no duplicate id.
- `libs` → **`dependencies`**; the FFI symbol counts appear ONLY when a probe ran, so a
  service/database dependency carries just `{loaded, error?}`.
The five states and the verdict rule (excludes blocked/off) are unchanged. Spec:
[`spec/readiness.md`](../../spec/readiness.md).

## 0.6.0 — 2026-09-01

The full ironmcp substrate, in parity with the TypeScript, PHP, and Dart kits and proven
by the shared conformance corpus.

### Added
- **Self-discovery registry** — a server registers itself; agents enumerate every live
  ironmcp server (namespace, port, capabilities). Registry file format byte-identical
  across all four language kits (`started_at` normalised to millisecond-Z).
- **Structured readiness + health** — a full readiness report (feature / native-library /
  data-file status with a verdict that excludes environmental blocks) and a lightweight
  health tool; `code_sha` to detect a server running older code than expected.
- **Transport hardening** — bearer-guarded `/mcp` (fail-closed, constant-time), an open
  `/healthz` naming capabilities, and a DNS-rebinding host guard on by default
  (RFC 7230 case-insensitive, IPv6-bracket aware), with Windows TIME_WAIT port-retry.
- **Content + clean-quit helpers** — image/binary tool results with an empty-capture
  guard, and a fenced, ordered, idempotent shutdown scaffold with an honest `quit` tool.

## 0.3.0 — 2026-08-31

Package renamed **`mcpkit` → `ironmcp`** (flat, v2-only). The MCP v2 port, and the seed of ironmcp-the-standard.

### Added
- **`ironmcp`** — the strict-args guarantee as an MCP v2 `ServerMiddleware`
  (`mcp>=2`). Attach it, don't subclass:
  - `strict_server(name=..., version=...)` — an `MCPServer` guarded by
    `StrictArgsMiddleware`; refuses unknown tool arguments (never silently drops them)
    and advertises `additionalProperties: false` (advertisement == runtime). Honours the
    `additionalProperties: true` opt-out.
  - `assert_enforces_v2` / `aassert_enforces_v2` — the ADVERTISEMENT == RUNTIME
    conformance check, driven through a real client↔server session.
  - `run_corpus(server, "conformance/cases")` — runs the language-neutral conformance
    corpus (`conformance/`).
  - `health_payload` / `code_sha` — agent-interrogable liveness.
  - `make_bearer_asgi(app, expected_token=...)` — fail-closed bearer auth at the HTTP
    transport seam (401 + `WWW-Authenticate`).
- **`spec/`** — the language-neutral behavioural contract (strict-args, conformance).
- **`conformance/`** — the JSON conformance corpus + case schema. The seed for kits in
  every language.

### Changed
- Renamed from `mcpkit`; now a flat, v2-only package (`import ironmcp`). Floor `mcp>=2,<3`.
  

## 0.2.1 and earlier

v1 (FastMCP): `StrictArgsMCP`, `assert_enforces`, `attach_healthz`, `bearer_middleware`,
`verify_seams`, vendoring. See git history.
