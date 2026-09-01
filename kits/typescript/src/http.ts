// Supervised streamable-HTTP serving in one call: a bearer-guarded /mcp, an open /healthz that
// names a capability, fail-closed on an empty/whitespace token. STATELESS mode
// (sessionIdGenerator: undefined) needs a FRESH server + transport PER REQUEST — reusing one
// throws on request #2 because request IDs collide across connections (proven in scarlight
// src/mcp/http.js). So serveHttp takes a factory, not a single server.
import { createServer as createHttpServer, type IncomingMessage, type ServerResponse } from "node:http";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { bearerOk, HostGuard } from "./auth.js";
import { codeSha } from "./health.js";

export type ServeHttpOpts = {
  token: string;
  host?: string;
  port: number;
  healthz?: boolean;
  capabilities?: Record<string, unknown>;
  codeSha?: string;
  /** DNS-rebinding host allowlist. Omit to derive [host, localhost, 127.0.0.1] (port-insensitive).
   *  The guard is ON by default (invariant #4); pass hostGuard:false only for a deliberate opt-out. */
  allowedHosts?: string[];
  hostGuard?: boolean;
  /** F3 non-fatal port-retry: bind attempts on EADDRINUSE (the Windows TIME_WAIT case). */
  maxRetries?: number;
  retryDelayMs?: number;
};

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

/** Default: a bind error worth retrying is a port still held by a prior process. */
export function isPortBusy(err: unknown): boolean {
  return (err as NodeJS.ErrnoException | undefined)?.code === "EADDRINUSE";
}

export type BindRetryResult = { ok: boolean; attempts: number; lastError: unknown };

/** The testable, NON-FATAL port-retry core (loqu8 invariant #2). Retries [bind] up to
 *  [maxRetries] while [isRetriable] holds (default: EADDRINUSE — the Windows TIME_WAIT case where a
 *  prior process still holds the port), waiting [retryDelayMs] between attempts. On final failure
 *  it RECORDS lastError and returns ok:false rather than throwing, so a server that cannot bind
 *  does not crash the app. A non-retriable error fails fast (no retry) and is likewise non-fatal. */
export async function bindWithRetry(
  bind: () => Promise<void>,
  opts: {
    maxRetries?: number;
    retryDelayMs?: number;
    isRetriable?: (err: unknown) => boolean;
    onLog?: (message: string) => void;
  } = {},
): Promise<BindRetryResult> {
  const maxRetries = opts.maxRetries ?? 3;
  const retryDelayMs = opts.retryDelayMs ?? 2000;
  const isRetriable = opts.isRetriable ?? isPortBusy;
  let lastError: unknown = null;
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      await bind();
      return { ok: true, attempts: attempt, lastError: null };
    } catch (e) {
      lastError = e;
      if (!isRetriable(e)) return { ok: false, attempts: attempt, lastError: e }; // fail fast
      if (attempt < maxRetries) {
        opts.onLog?.(`bind busy (attempt ${attempt}/${maxRetries}): retrying in ${retryDelayMs}ms`);
        await sleep(retryDelayMs);
      }
    }
  }
  return { ok: false, attempts: maxRetries, lastError };
}

/** Build a node http request handler: /healthz open, /mcp bearer-guarded then dispatched to a
 *  fresh stateless transport. Throws on an empty/whitespace token (fails closed). */
export function buildHttpHandler(makeServer: () => McpServer, opts: ServeHttpOpts) {
  const token = (opts.token ?? "").trim();
  if (!token) throw new Error("serveHttp token must be non-empty — HTTP serving fails closed");
  const caps = opts.capabilities ?? { strict_args: true, ironmcp: true };
  const sha = opts.codeSha ?? codeSha();
  const withHealthz = opts.healthz ?? true;

  // Host-guard ON by default (invariant #4). Derive an allowlist from the bind host when the caller
  // gives none; a rebinding attacker's Host is then refused while local/WSL reach still works.
  const host = opts.host ?? "127.0.0.1";
  const guardOn = opts.hostGuard ?? true;
  const guard = guardOn
    ? new HostGuard(opts.allowedHosts ?? [host, "localhost", "127.0.0.1"])
    : undefined;

  return async (req: IncomingMessage, res: ServerResponse) => {
    const url = new URL(req.url ?? "/", "http://localhost");

    if (guard && !guard.accepts(req.headers["host"])) {
      res.writeHead(403, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "forbidden host" }));
      return;
    }

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

  // One bind attempt: listen, resolving on 'listening' and rejecting on 'error' (EADDRINUSE etc).
  const bindOnce = () =>
    new Promise<void>((resolve, reject) => {
      const onError = (e: unknown) => {
        httpServer.removeListener("listening", onListening);
        reject(e);
      };
      const onListening = () => {
        httpServer.removeListener("error", onError);
        resolve();
      };
      httpServer.once("error", onError);
      httpServer.once("listening", onListening);
      httpServer.listen(opts.port, host);
    });

  const result = await bindWithRetry(bindOnce, {
    maxRetries: opts.maxRetries,
    retryDelayMs: opts.retryDelayMs,
  });
  if (!result.ok) throw result.lastError ?? new Error("serveHttp: could not bind port");

  return {
    url: `http://${host}:${opts.port}`,
    close: () => new Promise<void>((r) => httpServer.close(() => r())),
  };
}
