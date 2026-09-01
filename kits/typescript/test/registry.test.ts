import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { promises as fs } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { IronMcpRegistry, IronMcpEntry } from "../src/registry.js";

let dir: string;
beforeEach(async () => {
  dir = await fs.mkdtemp(join(tmpdir(), "ironmcp_reg_ts_"));
});
afterEach(async () => {
  await fs.rm(dir, { recursive: true, force: true });
});

describe("IronMcpRegistry", () => {
  it("concurrent registers do not lose an entry (lock closes TOCTOU, #9)", async () => {
    const reg = new IronMcpRegistry({ dir, isPidAlive: () => true });
    await Promise.all([
      reg.register(new IronMcpEntry({ id: "a", namespace: "test", pid: 1 })),
      reg.register(new IronMcpEntry({ id: "b", namespace: "test", pid: 2 })),
      reg.register(new IronMcpEntry({ id: "c", namespace: "test", pid: 3 })),
      reg.register(new IronMcpEntry({ id: "d", namespace: "test", pid: 4 })),
    ]);
    const live = await reg.discover();
    expect(new Set(live.map((e) => e.id))).toEqual(new Set(["a", "b", "c", "d"]));
  });

  it("discover prunes a dead pid and rewrites the file (lazy GC, #10)", async () => {
    const reg = new IronMcpRegistry({ dir, isPidAlive: (pid) => pid !== 2 });
    await reg.register(new IronMcpEntry({ id: "a", namespace: "test", pid: 1 }));
    await reg.register(new IronMcpEntry({ id: "b", namespace: "test", pid: 2 })); // dead
    expect(new Set((await reg.discover()).map((e) => e.id))).toEqual(new Set(["a"]));
    // rewritten: a second discover still only sees the live one
    expect(new Set((await reg.discover()).map((e) => e.id))).toEqual(new Set(["a"]));
    // and the on-disk file no longer holds the dead entry
    const onDisk = JSON.parse(await fs.readFile(join(dir, "registry.json"), "utf8"));
    expect(Object.keys(onDisk)).toEqual(["a"]);
  });

  it("unregister removes an entry", async () => {
    const reg = new IronMcpRegistry({ dir, isPidAlive: () => true });
    await reg.register(new IronMcpEntry({ id: "a", namespace: "test", pid: 1 }));
    await reg.unregister("a");
    expect(await reg.discover()).toEqual([]);
  });

  it("entry JSON is language-neutral and carries NO hand-kept tool list (#3)", () => {
    const j = new IronMcpEntry({
      id: "x",
      namespace: "ns",
      pid: 9,
      host: "127.0.0.1",
      port: 8080,
      transport: "http",
      version: "1.0",
      codeSha: "abc123",
      capabilities: { tools: {} },
    }).toJSON();
    expect(j.code_sha).toBe("abc123");
    expect(typeof j.started_at).toBe("string");
    expect(j).not.toHaveProperty("tools"); // honesty: no drifting count
    const e = IronMcpEntry.fromJSON(j);
    expect(e.id).toBe("x");
    expect(e.port).toBe(8080);
    expect(e.transport).toBe("http");
  });

  it("started_at is ISO-8601 UTC and the file is flat-keyed-by-id (Dart-compatible fabric)", async () => {
    const reg = new IronMcpRegistry({ dir, isPidAlive: () => true });
    await reg.register(new IronMcpEntry({ id: "srv1", namespace: "ns", pid: 1, port: 9000 }));
    const onDisk = JSON.parse(await fs.readFile(join(dir, "registry.json"), "utf8"));
    // top level keyed by entry id, matching Dart `map[entry.id] = entry.toJson()`
    expect(Object.keys(onDisk)).toEqual(["srv1"]);
    expect(onDisk.srv1.namespace).toBe("ns");
    // ISO-8601 UTC (trailing Z), parseable back to a Date
    expect(onDisk.srv1.started_at).toMatch(/T.*Z$/);
    expect(Number.isNaN(new Date(onDisk.srv1.started_at).getTime())).toBe(false);
  });

  it("a stale lock left by a crashed holder is stolen so writes still land", async () => {
    // Pre-create the lock and back-date it well past staleLockAfter.
    const lock = join(dir, "registry.json.lock");
    await fs.writeFile(lock, "");
    const old = new Date(Date.now() - 60_000);
    await fs.utimes(lock, old, old);
    const reg = new IronMcpRegistry({ dir, isPidAlive: () => true, staleLockAfterMs: 30_000 });
    await reg.register(new IronMcpEntry({ id: "a", namespace: "test", pid: 1 }));
    expect((await reg.discover()).map((e) => e.id)).toEqual(["a"]);
  });
});
