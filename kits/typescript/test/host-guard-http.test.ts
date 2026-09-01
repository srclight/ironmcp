import { describe, it, expect, afterEach } from "vitest";
import { request } from "node:http";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { serveHttp } from "../src/http.js";

function probeFactory() {
  return () => new McpServer({ name: "probe", version: "0.0.0" });
}

// Raw request so we can force the Host header (fetch/undici forbids setting it).
function raw(port: number, host: string, path: string): Promise<number> {
  return new Promise((resolve, reject) => {
    const req = request(
      { host: "127.0.0.1", port, path, method: "POST", headers: { Host: host } },
      (res) => {
        res.resume();
        resolve(res.statusCode ?? 0);
      },
    );
    req.on("error", reject);
    req.end();
  });
}

let close: (() => Promise<void>) | undefined;
afterEach(async () => {
  await close?.();
  close = undefined;
});

describe("host guard over HTTP (default ON — invariant #4)", () => {
  it("rejects a rebinding Host with 403 before bearer is even checked", async () => {
    const srv = await serveHttp(probeFactory(), { token: "secret", port: 8789 });
    close = srv.close;
    expect(await raw(8789, "evil.example.com", "/mcp")).toBe(403);
    expect(await raw(8789, "evil.example.com", "/healthz")).toBe(403);
  });

  it("an allowed Host passes the guard, then bearer applies (401 without a token)", async () => {
    const srv = await serveHttp(probeFactory(), { token: "secret", port: 8788 });
    close = srv.close;
    // localhost is in the default allowlist; guard passes, missing bearer -> 401.
    expect(await raw(8788, "localhost:8788", "/mcp")).toBe(401);
    expect(await raw(8788, "127.0.0.1:8788", "/mcp")).toBe(401);
  });

  it("forwards an explicit allowedHosts into the guard on the convenience serve path", async () => {
    // The one-call convenience entrypoint must let a caller ENABLE the rebinding guard with a
    // custom allowlist (invariant #4). Only "trusted.example" is allowed here; the default
    // localhost/127.0.0.1 derivation is replaced, so even localhost is refused.
    const srv = await serveHttp(probeFactory(), {
      token: "secret",
      port: 8786,
      allowedHosts: ["trusted.example", "trusted.example:8786"],
    });
    close = srv.close;
    expect(await raw(8786, "trusted.example:8786", "/mcp")).toBe(401); // allowed host -> bearer gate
    expect(await raw(8786, "evil.example.com", "/mcp")).toBe(403); // rebinding host refused
    expect(await raw(8786, "localhost:8786", "/mcp")).toBe(403); // not in the custom allowlist
  });

  it("hostGuard:false disables the check (opt-out)", async () => {
    const srv = await serveHttp(probeFactory(), { token: "secret", port: 8787, hostGuard: false });
    close = srv.close;
    // guard off: a foreign Host is no longer 403; it reaches the bearer gate -> 401.
    expect(await raw(8787, "evil.example.com", "/mcp")).toBe(401);
  });
});
