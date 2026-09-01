# Changelog

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
