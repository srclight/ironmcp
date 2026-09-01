import { describe, it, expect } from "vitest";
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";
import { guardServer, guardCallTool, guardListTools } from "../src/guard.js";

const TOOLS = [
  { name: "echo", description: "echo", inputSchema: { type: "object", properties: { a: {}, b: {} } } },
  { name: "ping", description: "ping", inputSchema: { type: "object", properties: {} } },
];

function buildLowLevel() {
  const s = new Server({ name: "probe", version: "0" }, { capabilities: { tools: {} } });
  s.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOLS }));
  s.setRequestHandler(CallToolRequestSchema, async (req: any) => ({
    content: [{ type: "text", text: `ran ${req.params.name}` }],
  }));
  return s;
}

async function connect(s: Server) {
  const [ct, st] = InMemoryTransport.createLinkedPair();
  await s.connect(st);
  const c = new Client({ name: "t", version: "0" });
  await c.connect(ct);
  return { c, close: async () => { await c.close(); await s.close(); } };
}

describe("guardServer (low-level, the sugar)", () => {
  it("refuses an unknown arg on the wire and never runs the tool", async () => {
    const { c, close } = await connect(guardServer(buildLowLevel(), { reconnectHint: "check status" }));
    try {
      const r: any = await c.callTool({ name: "echo", arguments: { a: "x", typo: 1 } });
      expect(r.isError).toBe(true);
      const text = r.content.map((x: any) => x.text).join(" ");
      expect(text).toContain("unknown argument(s): typo");
      expect(text).not.toContain("ran echo");
    } finally { await close(); }
  });
  it("passes a known call through to the real handler", async () => {
    const { c, close } = await connect(guardServer(buildLowLevel()));
    try {
      const r: any = await c.callTool({ name: "echo", arguments: { a: "x", b: "y" } });
      expect(r.isError).toBeFalsy();
      expect(r.content.map((x: any) => x.text).join(" ")).toContain("ran echo");
    } finally { await close(); }
  });
  it("refuses an extra on a zero-arg tool", async () => {
    const { c, close } = await connect(guardServer(buildLowLevel()));
    try {
      expect((await c.callTool({ name: "ping", arguments: { typo: 1 } }) as any).isError).toBe(true);
    } finally { await close(); }
  });
  it("stamps additionalProperties:false on the advertised list AT THE WIRE", async () => {
    const { c, close } = await connect(guardServer(buildLowLevel()));
    try {
      const tools = (await c.listTools()).tools;
      expect(tools.find((t) => t.name === "echo")!.inputSchema.additionalProperties).toBe(false);
      expect(tools.find((t) => t.name === "ping")!.inputSchema.additionalProperties).toBe(false);
    } finally { await close(); }
  });

  it("works when guardServer is called BEFORE the app registers its handlers (the setRequestHandler patch branch)", async () => {
    // Every other test wraps an already-registered server (the re-wrap branch). Here we guard a
    // BARE server first, THEN register — exercising the patched setRequestHandler that wraps future
    // registrations (guard.ts lines 120-125). A ref-identity mismatch on the request schemas would
    // silently skip wrapping and this test would catch it.
    const s = new Server({ name: "probe", version: "0" }, { capabilities: { tools: {} } });
    guardServer(s, { reconnectHint: "check status" }); // guard FIRST
    s.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOLS })); // register AFTER
    s.setRequestHandler(CallToolRequestSchema, async (req: any) => ({
      content: [{ type: "text", text: `ran ${req.params.name}` }],
    }));
    const { c, close } = await connect(s);
    try {
      const tools = (await c.listTools()).tools;
      expect(tools.find((t) => t.name === "echo")!.inputSchema.additionalProperties).toBe(false);
      const bad: any = await c.callTool({ name: "echo", arguments: { a: "x", typo: 1 } });
      expect(bad.isError).toBe(true);
      expect(bad.content.map((x: any) => x.text).join(" ")).toContain("unknown argument(s): typo");
      const ok: any = await c.callTool({ name: "echo", arguments: { a: "x", b: "y" } });
      expect(ok.isError).toBeFalsy();
      expect(ok.content.map((x: any) => x.text).join(" ")).toContain("ran echo");
    } finally { await close(); }
  });

  it("a refusal reports the ACCEPTED keys in structuredContent, not just the unknown ones", async () => {
    const { c, close } = await connect(guardServer(buildLowLevel()));
    try {
      const r: any = await c.callTool({ name: "echo", arguments: { a: "x", typo: 1 } });
      expect(r.isError).toBe(true);
      expect(r.structuredContent.ironmcp.refused).toBe(true);
      expect(r.structuredContent.ironmcp.unknown).toContain("typo");
      // the machine-readable twin also names what WOULD have been accepted
      expect(r.structuredContent.ironmcp.accepted).toEqual(expect.arrayContaining(["a", "b"]));
    } finally { await close(); }
  });

  it("cold CallTool before any ListTools FAILS OPEN when the list handler THROWS (never bricks the call)", async () => {
    // populated=false and the list handler cannot answer: the internal cold-populate try/catch
    // (guard.ts 94-96) swallows the throw, schemas stays empty, and checkUnknownArgs(undefined,…)
    // is permissive. The tool runs rather than the whole call bricking.
    const s = new Server({ name: "probe", version: "0" }, { capabilities: { tools: {} } });
    s.setRequestHandler(ListToolsRequestSchema, async () => {
      throw new Error("list unavailable");
    });
    s.setRequestHandler(CallToolRequestSchema, async (req: any) => ({
      content: [{ type: "text", text: `ran ${req.params.name}` }],
    }));
    guardServer(s);
    const { c, close } = await connect(s);
    try {
      // No listTools() first -> the guard's cold-populate path runs and its listHandler throws.
      const r: any = await c.callTool({ name: "echo", arguments: { a: "x", surprise: 1 } });
      expect(r.isError).toBeFalsy(); // fail OPEN, not refused, not crashed
      expect(r.content.map((x: any) => x.text).join(" ")).toContain("ran echo");
    } finally { await close(); }
  });
});

describe("guardCallTool + guardListTools (the primary primitives, composed by hand)", () => {
  it("work standalone without guardServer's monkey-patch", async () => {
    const schemas = new Map<string, any>();
    const s = new Server({ name: "probe", version: "0" }, { capabilities: { tools: {} } });
    s.setRequestHandler(ListToolsRequestSchema, guardListTools(async () => ({ tools: TOOLS }), schemas));
    s.setRequestHandler(
      CallToolRequestSchema,
      guardCallTool(async (req: any) => ({ content: [{ type: "text", text: `ran ${req.params.name}` }] }), schemas),
    );
    const { c, close } = await connect(s as any);
    try {
      // list first so the CallTool guard has the schema captured
      const tools = (await c.listTools()).tools;
      expect(tools.find((t) => t.name === "echo")!.inputSchema.additionalProperties).toBe(false);
      expect((await c.callTool({ name: "echo", arguments: { a: "x", typo: 1 } }) as any).isError).toBe(true);
      expect((await c.callTool({ name: "echo", arguments: { a: "x", b: "y" } }) as any).isError).toBeFalsy();
    } finally { await close(); }
  });
});
