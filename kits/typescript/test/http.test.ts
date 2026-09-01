import { describe, it, expect, afterEach } from "vitest";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { z } from "zod";
import { serveHttp } from "../src/http.js";

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
