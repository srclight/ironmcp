// LIVE ROUND-TRIP CONFORMANCE — advertisement == runtime, proven over the REAL transport.
//
// Pure guard unit tests (strict.test.ts) exercise checkUnknownArgs in isolation; they cannot
// see a transport-level regression (the Dart kit shipped one that the pure tests missed). This
// file drives a real Client <-> Server MCP session over the SDK's in-memory pair transport and
// asserts that what a HARDENED server ADVERTISES in tools/list (additionalProperties:false plus
// its declared property set) is EXACTLY what it ENFORCES in tools/call. The refused argument is
// derived from the advertised schema itself, so the two can never silently diverge.
import { describe, it, expect } from "vitest";
import { buildBareServer, connect } from "./fixtures.js";
import { strictServer } from "../src/register.js";

describe("live round-trip (client<->server over in-memory transport)", () => {
  it("valid args -> the tool RUNS and returns its result", async () => {
    const { client, close } = await connect(strictServer(buildBareServer()));
    try {
      const r: any = await client.callTool({ name: "echo", arguments: { a: "x", b: "y" } });
      expect(r.isError).toBeFalsy();
      expect((r.content ?? []).map((c: any) => c.text ?? "").join(" ")).toContain("x|y");
    } finally {
      await close();
    }
  });

  it("an UNDECLARED extra arg -> the call is REFUSED and the response indicates the error", async () => {
    const { client, close } = await connect(strictServer(buildBareServer(), { reconnectHint: "check pack_status" }));
    try {
      const r: any = await client.callTool({ name: "echo", arguments: { a: "x", nope: 1 } });
      expect(r.isError).toBe(true);
      const text = (r.content ?? []).map((c: any) => c.text ?? "").join(" ");
      expect(text).toContain("unknown argument(s): nope");
      // machine-readable twin, same session, same wire
      expect(r.structuredContent?.ironmcp).toMatchObject({ refused: true, tool: "echo" });
      expect(r.structuredContent.ironmcp.unknown).toContain("nope");
    } finally {
      await close();
    }
  });

  it("advertisement == runtime: every tool the server ADVERTISES closed is enforced closed at CALL time", async () => {
    // One session. List first (as a real client does), then, for each advertised tool, send a key
    // that its advertised schema does NOT declare and prove the live call refuses it. This closes
    // the loop the Dart transport bug slipped through: the schema on the wire == the schema enforced.
    const { client, close } = await connect(strictServer(buildBareServer()));
    try {
      const tools = (await client.listTools()).tools;
      expect(tools.length).toBeGreaterThanOrEqual(2);
      for (const t of tools) {
        // ADVERTISED: closed schema on the wire.
        expect(t.inputSchema.additionalProperties, `${t.name} must advertise additionalProperties:false`).toBe(false);
        const declared = new Set(Object.keys(t.inputSchema.properties ?? {}));
        const intruder = "__undeclared_probe__";
        expect(declared.has(intruder)).toBe(false);
        // RUNTIME: the same undeclared key is refused at call time.
        const r: any = await client.callTool({ name: t.name, arguments: { [intruder]: 1 } });
        expect(r.isError, `${t.name}: advertised closed but accepted an undeclared arg at runtime`).toBe(true);
        expect(r.structuredContent?.ironmcp?.unknown).toContain(intruder);
      }
    } finally {
      await close();
    }
  });

  it("the same probe on a BARE server SILENTLY DROPS the extra (proves the round-trip can catch a regression)", async () => {
    // A test that never watches the unhardened path pass-through is theatre. The bare SDK server
    // drops the undeclared arg and runs anyway — advertisement (open) == runtime (open), the wrong
    // guarantee. This is exactly the failure the hardened case above must NOT exhibit.
    const { client, close } = await connect(buildBareServer());
    try {
      const r: any = await client.callTool({ name: "echo", arguments: { a: "x", nope: 1 } });
      expect(r.isError).toBeFalsy(); // silently accepted — the very bug ironmcp exists to kill
      expect((r.content ?? []).map((c: any) => c.text ?? "").join(" ")).toContain("x|");
    } finally {
      await close();
    }
  });
});
