// The low-level Server adapter. The explicit wrappers are the PRIMARY primitives (GROMIT:
// monkey-patching a method is fragile — the wrappers are what we test and document).
// guardServer is sugar that composes them by patching setRequestHandler.
import type { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";
import { checkUnknownArgs, stampClosed, type JsonSchema } from "./strict.js";

type ToolDef = { name: string; inputSchema?: JsonSchema; [k: string]: unknown };
type Schemas = Map<string, JsonSchema | undefined>;
type Handler = (req: any, extra: any) => any;

/**
 * Wrap a ListTools handler so every emitted tool's schema is stamped closed AT THE WIRE
 * (K9: stamp the serialized output the client will see, never a pre-serialization Zod shape).
 * Captures each tool's schema into `schemas` so the CallTool guard can read it.
 */
export function guardListTools(handler: Handler, schemas: Schemas): Handler {
  return async (req, extra) => {
    const out = await handler(req, extra);
    const tools: ToolDef[] = (out?.tools ?? []).map((t: ToolDef) => {
      schemas.set(t.name, t.inputSchema);
      return { ...t, inputSchema: stampClosed(t.inputSchema) };
    });
    return { ...out, tools };
  };
}

/** Wrap a CallTool handler so unknown args are refused before the real handler runs. */
export function guardCallTool(
  handler: Handler,
  schemas: Schemas,
  opts: { reconnectHint?: string } = {},
): Handler {
  return async (req, extra) => {
    const name = req?.params?.name as string;
    const args = (req?.params?.arguments ?? {}) as Record<string, unknown>;
    const known = checkUnknownArgs(schemas.get(name), args, {
      toolName: name,
      reconnectHint: opts.reconnectHint,
    });
    if (!known.ok)
      return {
        content: [{ type: "text", text: known.message }],
        // The prose is human/agent-readable; structuredContent is the same facts machine-
        // readable, so an agent parses unknown/accepted instead of scraping the text.
        structuredContent: {
          ironmcp: { refused: true, tool: name, unknown: known.unknown, accepted: known.accepted },
        },
        isError: true,
      };
    return handler(req, extra);
  };
}

/**
 * Sugar: apply the guard to a low-level Server, ORDER-INDEPENDENTLY. It both re-wraps any
 * tools/list + tools/call handlers already registered AND patches setRequestHandler so future
 * registrations are wrapped too — so it works whether called before or after the app registers
 * its handlers (GROMIT: never depend on call order). If a CallTool arrives before any ListTools
 * ran, `schemas` is empty and checkUnknownArgs(undefined, …) is permissive (state 1) — a
 * deliberate fail-open, never a crash.
 */
export function guardServer(server: Server, opts: { reconnectHint?: string } = {}): Server {
  const schemas: Schemas = new Map();
  const LIST = (ListToolsRequestSchema as any).shape.method.value as string; // "tools/list"
  const CALL = (CallToolRequestSchema as any).shape.method.value as string; // "tools/call"
  const reg = (server as any)._requestHandlers as Map<string, Handler> | undefined;

  // The list handler (raw or already-registered) doubles as the schema source: a real client
  // lists before it calls, but we do not depend on that — on a cold call we populate from it.
  let listHandler: Handler | undefined;
  let populated = false;

  const captureList = (h: Handler): Handler => {
    listHandler = h;
    return async (req, extra) => {
      const out = await h(req, extra);
      const tools: ToolDef[] = (out?.tools ?? []).map((t: ToolDef) => {
        schemas.set(t.name, t.inputSchema);
        return { ...t, inputSchema: stampClosed(t.inputSchema) };
      });
      populated = true;
      return { ...out, tools };
    };
  };

  const guardedCall = (h: Handler): Handler => async (req, extra) => {
    const name = req?.params?.name as string;
    if (!populated && listHandler) {
      try {
        const out = await listHandler({ method: LIST, params: {} } as any, extra);
        for (const t of out?.tools ?? []) schemas.set(t.name, t.inputSchema);
        populated = true;
      } catch {
        /* fail open — a list handler that will not answer must not brick the call */
      }
    }
    const args = (req?.params?.arguments ?? {}) as Record<string, unknown>;
    const known = checkUnknownArgs(schemas.get(name), args, { toolName: name, reconnectHint: opts.reconnectHint });
    if (!known.ok)
      return {
        content: [{ type: "text", text: known.message }],
        // The prose is human/agent-readable; structuredContent is the same facts machine-
        // readable, so an agent parses unknown/accepted instead of scraping the text.
        structuredContent: {
          ironmcp: { refused: true, tool: name, unknown: known.unknown, accepted: known.accepted },
        },
        isError: true,
      };
    return h(req, extra);
  };

  // 1. Re-wrap handlers already registered (the app constructed + registered, then called us).
  if (reg) {
    if (reg.has(LIST)) reg.set(LIST, captureList(reg.get(LIST)!));
    if (reg.has(CALL)) reg.set(CALL, guardedCall(reg.get(CALL)!));
  }

  // 2. Patch setRequestHandler so any FUTURE registration is wrapped as well.
  const original = server.setRequestHandler.bind(server);
  (server as any).setRequestHandler = (schema: unknown, handler: Handler) => {
    if (schema === ListToolsRequestSchema) return original(schema as any, captureList(handler) as any);
    if (schema === CallToolRequestSchema) return original(schema as any, guardedCall(handler) as any);
    return original(schema as any, handler as any);
  };
  return server;
}
