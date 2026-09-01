// Supervised streamable-HTTP serving in one call: a bearer-guarded /mcp, an open /healthz that
// names a capability, fail-closed on an empty/whitespace token. STATELESS mode
// (sessionIdGenerator: undefined) needs a FRESH server + transport PER REQUEST — reusing one
// throws on request #2 because request IDs collide across connections (proven in scarlight
// src/mcp/http.js). So serveHttp takes a factory, not a single server.
import { createServer as createHttpServer, type IncomingMessage, type ServerResponse } from "node:http";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { bearerOk } from "./auth.js";
import { codeSha } from "./health.js";

export type ServeHttpOpts = {
  token: string;
  host?: string;
  port: number;
  healthz?: boolean;
  capabilities?: Record<string, unknown>;
  codeSha?: string;
};

/** Build a node http request handler: /healthz open, /mcp bearer-guarded then dispatched to a
 *  fresh stateless transport. Throws on an empty/whitespace token (fails closed). */
export function buildHttpHandler(makeServer: () => McpServer, opts: ServeHttpOpts) {
  const token = (opts.token ?? "").trim();
  if (!token) throw new Error("serveHttp token must be non-empty — HTTP serving fails closed");
  const caps = opts.capabilities ?? { strict_args: true, ironmcp: true };
  const sha = opts.codeSha ?? codeSha();
  const withHealthz = opts.healthz ?? true;

  return async (req: IncomingMessage, res: ServerResponse) => {
    const url = new URL(req.url ?? "/", "http://localhost");

    if (withHealthz && req.method === "GET" && url.pathname === "/healthz") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ ok: true, codeSha: sha, transport: "streamable-http", capabilities: caps }));
      return;
    }
    if (url.pathname !== "/mcp") {
      res.writeHead(404, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "not found", endpoints: ["/mcp", "/healthz"] }));
      return;
    }
    if (!bearerOk(req.headers["authorization"], token)) {
      res.writeHead(401, { "Content-Type": "application/json", "WWW-Authenticate": "Bearer" });
      res.end(JSON.stringify({ error: "unauthorized" }));
      return;
    }

    // Stateless: a NEW server + transport per request. Reusing one throws on request #2.
    try {
      const server = makeServer();
      const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined });
      res.on("close", () => {
        transport.close?.();
        server.close?.();
      });
      await server.connect(transport);
      await transport.handleRequest(req, res);
    } catch {
      if (!res.headersSent) {
        res.writeHead(500, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "internal" }));
      }
    }
  };
}

/** Create + start a node http.Server for a hardened streamable-HTTP MCP daemon.
 *  async so buildHttpHandler's synchronous fail-closed throw surfaces as a rejected promise. */
export async function serveHttp(
  makeServer: () => McpServer,
  opts: ServeHttpOpts,
): Promise<{ url: string; close: () => Promise<void> }> {
  const handler = buildHttpHandler(makeServer, opts); // throws on a bad token -> rejection
  const host = opts.host ?? "127.0.0.1";
  const httpServer = createHttpServer((req, res) => {
    void handler(req, res);
  });
  return new Promise((resolve) => {
    httpServer.listen(opts.port, host, () =>
      resolve({
        url: `http://${host}:${opts.port}`,
        close: () => new Promise<void>((r) => httpServer.close(() => r())),
      }),
    );
  });
}
