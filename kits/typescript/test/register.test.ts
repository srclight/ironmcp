import { describe, it, expect } from "vitest";
import { buildBareServer, sessionCall, listTools, isError, resultText } from "./fixtures.js";
import { strictServer } from "../src/register.js";

describe("strictServer (high-level McpServer)", () => {
  it("refuses an unknown arg that the bare server would have dropped", async () => {
    const s = strictServer(buildBareServer(), { reconnectHint: "check status" });
    const r = await sessionCall(s, "echo", { a: "x", typo: 1 });
    expect(isError(r)).toBe(true);
    expect(resultText(r)).toContain("unknown argument(s): typo");
  });
  it("passes a known call through", async () => {
    const r = await sessionCall(strictServer(buildBareServer()), "echo", { a: "x", b: "y" });
    expect(isError(r)).toBeFalsy();
    expect(resultText(r)).toContain("x|y");
  });
  it("refuses an extra on the zero-arg tool the SDK left open", async () => {
    const r = await sessionCall(strictServer(buildBareServer()), "ping", { typo: 1 });
    expect(isError(r)).toBe(true);
  });
  it("advertises additionalProperties:false on every tool, uniformly", async () => {
    const tools = await listTools(strictServer(buildBareServer()));
    expect(tools.find((t) => t.name === "echo")!.inputSchema.additionalProperties).toBe(false);
    expect(tools.find((t) => t.name === "ping")!.inputSchema.additionalProperties).toBe(false);
  });
});
