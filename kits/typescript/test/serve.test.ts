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
});
