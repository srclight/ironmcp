import { describe, it, expect, afterEach } from "vitest";
import { createServer as createHttpServer, type IncomingMessage, type ServerResponse } from "node:http";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { z } from "zod";
import { serveHttp, buildHttpHandler, type ServeHttpOpts } from "../src/http.js";

// Stateless streamable-HTTP needs a fresh server per request, so serveHttp takes a factory.
function probeFactory() {
  return () => {
    const s = new McpServer({ name: "probe", version: "0.0.0" });
    s.registerTool("echo", { inputSchema: { a: z.string() } }, async ({ a }) => ({
      content: [{ type: "text", text: a }],
    }));
    return s;
  };
}

let close: (() => Promise<void>) | undefined;
afterEach(async () => {
  await close?.();
  close = undefined;
});

describe("serveHttp", () => {
  it("/healthz is open and names the capability", async () => {
    const srv = await serveHttp(probeFactory(), { token: "secret", port: 8798, capabilities: { strict_args: true } });
    close = srv.close;
    const r = await fetch(srv.url + "/healthz");
    expect(r.status).toBe(200);
    const body: any = await r.json();
    expect(body.ok).toBe(true);
    expect(typeof body.codeSha).toBe("string");
    expect(body.capabilities.strict_args).toBe(true);
  });

  it("/mcp requires a bearer token", async () => {
    const srv = await serveHttp(probeFactory(), { token: "secret", port: 8797 });
    close = srv.close;
    expect((await fetch(srv.url + "/mcp", { method: "POST" })).status).toBe(401);
    expect((await fetch(srv.url + "/mcp", { method: "POST", headers: { Authorization: "Bearer WRONG" } })).status).toBe(401);
  });

  it("fails closed on an empty or whitespace token", async () => {
    await expect(serveHttp(probeFactory(), { token: "", port: 8796 })).rejects.toThrow();
    await expect(serveHttp(probeFactory(), { token: "   ", port: 8795 })).rejects.toThrow();
  });

  it("reports a caller-supplied codeSha on /healthz", async () => {
    const srv = await serveHttp(probeFactory(), { token: "secret", port: 8794, codeSha: "deadbeef" });
    close = srv.close;
    const body: any = await (await fetch(srv.url + "/healthz")).json();
    expect(body.codeSha).toBe("deadbeef");
  });

  it("an unknown path returns 404 naming the endpoints", async () => {
    const srv = await serveHttp(probeFactory(), { token: "secret", port: 8792 });
    close = srv.close;
    const r = await fetch(srv.url + "/nope");
    expect(r.status).toBe(404);
    const body: any = await r.json();
    expect(body.error).toBe("not found");
    expect(body.endpoints).toEqual(["/mcp", "/healthz"]);
  });

  it("healthz:false makes GET /healthz a 404 (the endpoint is not mounted)", async () => {
    const srv = await serveHttp(probeFactory(), { token: "secret", port: 8791, healthz: false });
    close = srv.close;
    const r = await fetch(srv.url + "/healthz");
    expect(r.status).toBe(404);
    const body: any = await r.json();
    expect(body.error).toBe("not found");
  });

  // The committed reachability proof: a real server, a real streamable-HTTP client, /mcp answers.
  it("is reachable over a real streamable-HTTP round-trip", async () => {
    const srv = await serveHttp(probeFactory(), { token: "tok", port: 8793 });
    close = srv.close;
    const transport = new StreamableHTTPClientTransport(new URL(srv.url + "/mcp"), {
      requestInit: { headers: { Authorization: "Bearer tok" } },
    });
    const client = new Client({ name: "e2e", version: "0" });
    await client.connect(transport);
    const names = (await client.listTools()).tools.map((t) => t.name);
    expect(names).toEqual(["echo"]);
    await client.close();
  });
});

// A tiny ServerResponse stand-in so we can drive buildHttpHandler's error/edge branches without a
// socket — records the status and JSON body the handler wrote.
function mockRes() {
  return {
    statusCode: 0,
    body: "",
    headersSent: false,
    writeHead(code: number, _headers?: unknown) {
      this.statusCode = code;
      this.headersSent = true;
      return this;
    },
    end(chunk?: string) {
      if (chunk) this.body = chunk;
    },
    on() {
      /* no close event in these unit paths */
    },
  };
}
const mockReq = (method: string, url: string, headers: Record<string, string>) =>
  ({ method, url, headers }) as unknown as IncomingMessage;

const baseOpts: ServeHttpOpts = { token: "secret", port: 0, host: "127.0.0.1" };

describe("buildHttpHandler internal-error path", () => {
  it("returns 500 when makeServer() throws (the catch around per-request setup)", async () => {
    const handler = buildHttpHandler(
      () => {
        throw new Error("factory boom");
      },
      baseOpts,
    );
    const res = mockRes();
    // Host + bearer both valid so we reach the makeServer() call, which throws -> 500.
    await handler(
      mockReq("POST", "/mcp", { host: "localhost", authorization: "Bearer secret" }),
      res as unknown as ServerResponse,
    );
    expect(res.statusCode).toBe(500);
    expect(JSON.parse(res.body).error).toBe("internal");
  });

  it("404 body names the endpoints for an unknown path (unit)", async () => {
    const handler = buildHttpHandler(probeFactory(), baseOpts);
    const res = mockRes();
    await handler(mockReq("GET", "/random", { host: "localhost" }), res as unknown as ServerResponse);
    expect(res.statusCode).toBe(404);
    expect(JSON.parse(res.body).endpoints).toEqual(["/mcp", "/healthz"]);
  });
});

describe("serveHttp EADDRINUSE retry wiring (integration, not just the pure core)", () => {
  it("gives up after maxRetries when the port stays occupied, and rejects", async () => {
    // Occupy a port with a plain server, then ask serveHttp to bind the SAME port. serveHttp
    // re-calls httpServer.listen() across attempts; with the port held it exhausts retries.
    const port = 8786;
    const blocker = createHttpServer((_req, res) => res.end());
    await new Promise<void>((r) => blocker.listen(port, "127.0.0.1", r));
    try {
      await expect(
        serveHttp(probeFactory(), { token: "secret", port, maxRetries: 2, retryDelayMs: 5 }),
      ).rejects.toMatchObject({ code: "EADDRINUSE" });
    } finally {
      await new Promise<void>((r) => blocker.close(() => r()));
    }
  });

  it("recovers by RE-LISTENING on the same http.Server when the port frees mid-retry", async () => {
    // Prove the integration path, not just bindWithRetry: the port is busy on attempt 1, freed
    // during the retry delay, and serveHttp's re-listen on attempt 2 succeeds.
    const port = 8785;
    const blocker = createHttpServer((_req, res) => res.end());
    await new Promise<void>((r) => blocker.listen(port, "127.0.0.1", r));
    // free the port shortly after serveHttp starts retrying
    setTimeout(() => blocker.close(), 40).unref?.();
    const srv = await serveHttp(probeFactory(), { token: "secret", port, maxRetries: 10, retryDelayMs: 30 });
    close = srv.close;
    const r = await fetch(srv.url + "/healthz");
    expect(r.status).toBe(200);
  });
});
