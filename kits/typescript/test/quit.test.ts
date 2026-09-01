import { describe, it, expect, vi } from "vitest";
import { CleanQuit, replyThenQuit } from "../src/quit.js";

describe("CleanQuit", () => {
  it("steps run in order", async () => {
    const order: number[] = [];
    await new CleanQuit([
      async () => void order.push(1),
      async () => void order.push(2),
      async () => void order.push(3),
    ]).run();
    expect(order).toEqual([1, 2, 3]);
  });

  it("a throwing step does not abort the rest (invariant #5)", async () => {
    const order: number[] = [];
    const errored: number[] = [];
    await new CleanQuit(
      [
        async () => void order.push(1),
        async () => {
          throw new Error("boom");
        },
        async () => void order.push(3),
      ],
      (i) => void errored.push(i),
    ).run();
    expect(order).toEqual([1, 3]);
    expect(errored).toEqual([1]); // the throwing step's index
  });

  it("a THROWING onError handler does not abort the remaining steps (onError is itself fenced)", async () => {
    const order: number[] = [];
    await new CleanQuit(
      [
        async () => void order.push(1),
        async () => {
          throw new Error("step boom");
        },
        async () => void order.push(3),
        async () => void order.push(4),
      ],
      () => {
        throw new Error("reporter boom"); // a broken reporter must not strand shutdown
      },
    ).run();
    // step 2 threw, onError threw too, yet steps 3 and 4 still ran
    expect(order).toEqual([1, 3, 4]);
  });

  it("a throwing step with NO onError still runs the rest (absent handler is a no-op)", async () => {
    const order: number[] = [];
    await new CleanQuit([
      async () => void order.push(1),
      async () => {
        throw new Error("boom");
      },
      async () => void order.push(3),
    ]).run();
    expect(order).toEqual([1, 3]);
  });

  it("second run is a no-op (idempotent, invariant #6)", async () => {
    let count = 0;
    const q = new CleanQuit([async () => void count++]);
    await q.run();
    await q.run();
    expect(count).toBe(1);
    expect(q.hasRun).toBe(true);
  });

  it("replyThenQuit returns the result BEFORE the quit fires (invariant #1)", async () => {
    let quitFired = false;
    let resolveFired!: () => void;
    const fired = new Promise<void>((r) => (resolveFired = r));
    const r = replyThenQuit(
      "reply",
      async () => {
        quitFired = true;
        resolveFired();
      },
      0,
    );
    expect(r).toBe("reply");
    expect(quitFired).toBe(false); // reply returned first; quit not yet fired
    await fired;
    expect(quitFired).toBe(true);
  });

  it("replyThenQuit defaults to a ~300ms grace and fires quit after it", async () => {
    vi.useFakeTimers();
    try {
      let quitFired = false;
      const r = replyThenQuit("reply", () => {
        quitFired = true;
      }); // default delayMs
      expect(r).toBe("reply");
      // not fired before the grace elapses
      vi.advanceTimersByTime(299);
      expect(quitFired).toBe(false);
      // fires at the 300ms default
      vi.advanceTimersByTime(1);
      expect(quitFired).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });

  it("the pending quit timer is unref'd so it never holds the event loop open", () => {
    // Spy on setTimeout's returned handle to prove .unref() was called (invariant: a scheduled
    // quit must not, by itself, keep the process alive).
    let unrefCalled = false;
    const realSetTimeout = globalThis.setTimeout;
    const spy = vi.spyOn(globalThis, "setTimeout").mockImplementation(((fn: any, ms?: number, ...a: any[]) => {
      const t = realSetTimeout(fn, ms, ...a) as any;
      const realUnref = t.unref?.bind(t);
      t.unref = () => {
        unrefCalled = true;
        return realUnref?.();
      };
      return t;
    }) as any);
    try {
      replyThenQuit("reply", () => {}, 10_000);
      expect(unrefCalled).toBe(true);
    } finally {
      spy.mockRestore();
    }
  });
});
