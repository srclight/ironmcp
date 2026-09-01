import { describe, it, expect } from "vitest";
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
});
