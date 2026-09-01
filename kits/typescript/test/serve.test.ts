import { describe, it, expect } from "vitest";
import { bindWithRetry, isPortBusy } from "../src/http.js";

function eaddrinuse(): NodeJS.ErrnoException {
  const e = new Error("busy") as NodeJS.ErrnoException;
  e.code = "EADDRINUSE";
  return e;
}

describe("bindWithRetry (F3 non-fatal port-retry)", () => {
  it("retries on a busy port then succeeds (invariant #2)", async () => {
    let calls = 0;
    const r = await bindWithRetry(
      async () => {
        calls++;
        if (calls < 3) throw eaddrinuse();
      },
      { retryDelayMs: 0 },
    );
    expect(r.ok).toBe(true);
    expect(calls).toBe(3);
    expect(r.lastError).toBeNull(); // a retry that ultimately succeeds is not an error
  });

  it("gives up after maxRetries — non-fatal, records lastError", async () => {
    let calls = 0;
    const r = await bindWithRetry(
      async () => {
        calls++;
        throw eaddrinuse();
      },
      { retryDelayMs: 0 },
    );
    expect(r.ok).toBe(false); // does NOT throw
    expect(calls).toBe(3);
    expect((r.lastError as NodeJS.ErrnoException).code).toBe("EADDRINUSE");
  });

  it("a non-retriable error fails fast (no retry) and is non-fatal", async () => {
    let calls = 0;
    const r = await bindWithRetry(
      async () => {
        calls++;
        throw new Error("boom"); // no EADDRINUSE code
      },
      { retryDelayMs: 0 },
    );
    expect(r.ok).toBe(false);
    expect(calls).toBe(1);
    expect((r.lastError as Error).message).toBe("boom");
  });

  it("isPortBusy classifies only EADDRINUSE as retriable", () => {
    expect(isPortBusy(eaddrinuse())).toBe(true);
    expect(isPortBusy(new Error("nope"))).toBe(false);
    expect(isPortBusy(undefined)).toBe(false);
  });

  it("invokes onLog before each retry and honours a NON-DEFAULT maxRetries", async () => {
    const logs: string[] = [];
    let calls = 0;
    const r = await bindWithRetry(
      async () => {
        calls++;
        throw eaddrinuse(); // never succeeds
      },
      { maxRetries: 5, retryDelayMs: 0, onLog: (m) => logs.push(m) },
    );
    expect(r.ok).toBe(false);
    expect(calls).toBe(5); // custom maxRetries, not the default 3
    expect(r.attempts).toBe(5);
    // onLog fires between attempts (not after the final one): maxRetries-1 messages.
    expect(logs).toHaveLength(4);
    expect(logs[0]).toContain("attempt 1/5");
    expect(logs[3]).toContain("attempt 4/5");
  });

  it("onLog does NOT fire when the first bind succeeds", async () => {
    const logs: string[] = [];
    const r = await bindWithRetry(async () => {}, { retryDelayMs: 0, onLog: (m) => logs.push(m) });
    expect(r.ok).toBe(true);
    expect(logs).toEqual([]);
  });
});
