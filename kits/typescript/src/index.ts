// ironmcp — the hardening & conformance standard for MCP servers (TypeScript kit).
// The strict-args guarantee (refuse unknown tool arguments instead of silently dropping them;
// advertise exactly what you enforce) for the official @modelcontextprotocol/sdk, plus the
// shared conformance corpus, agent-interrogable health, and fail-closed bearer auth.
export { strictServer } from "./register.js";
export { guardServer, guardCallTool, guardListTools } from "./guard.js";
export { checkUnknownArgs, stampClosed, type JsonSchema, type ArgCheck } from "./strict.js";
export { unknownArgsMessage, DEFAULT_RECONNECT_HINT, MAX_ENUMERATED } from "./messages.js";
export { assertEnforces, loadCases, type CorpusResult } from "./corpus.js";
export { codeSha, healthPayload, IRONMCP_VERSION } from "./health.js";
export { bearerOk } from "./auth.js";
export { serveHttp, buildHttpHandler, type ServeHttpOpts } from "./http.js";
