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
export { bearerOk, HostGuard } from "./auth.js";
export {
  serveHttp,
  buildHttpHandler,
  bindWithRetry,
  isPortBusy,
  type ServeHttpOpts,
  type BindRetryResult,
} from "./http.js";
export {
  Results,
  MIN_BYTES,
  type ToolResult,
  type ContentBlock,
  type TextBlock,
  type ImageBlock,
  type AudioBlock,
} from "./results.js";
export { CleanQuit, replyThenQuit, type QuitStep } from "./quit.js";
export {
  IronMcpRegistry,
  IronMcpEntry,
  type IronMcpEntryInput,
  type IronMcpRegistryOpts,
} from "./registry.js";
export {
  ReadinessReport,
  type ReadinessStatus,
  type FeatureReadiness,
  type LibraryStatus,
  type DataFileStatus,
  type ReadinessReportInput,
} from "./readiness.js";
