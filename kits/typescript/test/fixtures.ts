import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { z } from "zod";

/** The fixture the corpus README mandates: a 2-arg tool and a 0-arg tool, UNGUARDED. */
export function buildBareServer(): McpServer {
  const s = new McpServer({ name: "probe", version: "0.0.0" });
  s.registerTool(
    "echo",
    { description: "echo", inputSchema: { a: z.string(), b: z.string().optional() } },
    async ({ a, b }) => ({ content: [{ type: "text", text: `${a}|${b ?? "default"}` }] }),
  );
  s.registerTool("ping", { description: "ping", inputSchema: {} }, async () => ({
    content: [{ type: "text", text: "pong" }],
  }));
  return s;
}

/** Open a real client<->server session over the SDK's in-memory transport pair. */
export async function connect(server: { connect: (t: unknown) => Promise<void>; close: () => Promise<void> }) {
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await server.connect(serverTransport);
  const client = new Client({ name: "test", version: "0.0.0" });
  await client.connect(clientTransport);
  return {
    client,
    close: async () => {
      await client.close();
      await server.close();
    },
  };
}

export async function sessionCall(server: any, tool: string, args: Record<string, unknown>) {
  const { client, close } = await connect(server);
  try {
    return await client.callTool({ name: tool, arguments: args });
  } finally {
    await close();
  }
}

export async function listTools(server: any) {
  const { client, close } = await connect(server);
  try {
    return (await client.listTools()).tools;
  } finally {
    await close();
  }
}

export function resultText(r: any): string {
  return (r.content ?? []).map((c: any) => c.text ?? "").join(" ");
}

export function isError(r: any): boolean {
  return r.isError === true;
}
