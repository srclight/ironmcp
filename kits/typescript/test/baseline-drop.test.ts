import { describe, it, expect } from "vitest";
import { buildBareServer, sessionCall, listTools, isError } from "./fixtures.js";

// A corpus never watched to FAIL against a bare server is theatre. These tests document the
// exact bug ironmcp closes on THIS SDK (v1.30 + zod v3), which is subtler than "no
// additionalProperties": the runtime silently strips unknown arguments even where the wire
// already claims additionalProperties:false. Advertisement and runtime disagree, the
// dangerous way — the catalog says closed while the runtime accepts-and-drops.
describe("baseline: the unguarded SDK is exactly the bug ironmcp fixes", () => {
  it("echo: runtime silently ACCEPTS an unknown arg even though the wire advertises closed", async () => {
    const tools = await listTools(buildBareServer());
    const echo = tools.find((t) => t.name === "echo")!;
    expect(echo.inputSchema.additionalProperties).toBe(false); // wire says closed...
    const r = await sessionCall(buildBareServer(), "echo", { a: "x", typo: "ignored" });
    expect(isError(r)).toBe(false); // ...runtime accepts and strips anyway — the incoherence
  });
  it("ping: the zero-arg tool does not even advertise closed, and accepts a typo", async () => {
    const tools = await listTools(buildBareServer());
    const ping = tools.find((t) => t.name === "ping")!;
    expect(ping.inputSchema.additionalProperties).not.toBe(false); // undefined, not closed
    const r = await sessionCall(buildBareServer(), "ping", { typo: 1 });
    expect(isError(r)).toBe(false); // runtime accepts the extra
  });
});
