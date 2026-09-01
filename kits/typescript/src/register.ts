// The high-level McpServer adapter. McpServer keeps its low-level Server at `.server` and
// installs its tools/list + tools/call handlers there; guardServer wraps those. Because
// guardServer is order-independent (re-wraps existing + patches future registrations) and
// stamps at the WIRE, it survives McpServer registering its handlers lazily on connect and
// the zod-to-json-schema serialization (K9: the stamp lands on the serialized output the
// client sees, so Zod v4 dropping additionalProperties from the shape does not defeat it).
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { guardServer } from "./guard.js";

export function strictServer(server: McpServer, opts: { reconnectHint?: string } = {}): McpServer {
  guardServer((server as any).server, opts);
  return server;
}
