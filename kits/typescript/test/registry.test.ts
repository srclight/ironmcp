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

  it("started_at is the CANONICAL registry format: ISO-8601 UTC, millisecond precision, trailing Z", async () => {
    // The estate canon is exactly YYYY-MM-DDTHH:mm:ss.sssZ (3 fractional digits, Z — never a
    // +00:00 offset, never 6-digit microseconds). Pin it so a future refactor can't drift the
    // registry.json off byte-parity with the other kits once they normalize to this shape.
    const reg = new IronMcpRegistry({ dir, isPidAlive: () => true });
    await reg.register(new IronMcpEntry({ id: "srv1", namespace: "ns", pid: 1 }));
    const onDisk = JSON.parse(await fs.readFile(join(dir, "registry.json"), "utf8"));
    expect(onDisk.srv1.started_at).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/);
    expect(onDisk.srv1.started_at).not.toContain("+00:00"); // not the Python-style offset
    expect(onDisk.srv1.started_at).not.toMatch(/\.\d{6}Z$/); // not Dart-style microseconds

    // A fixed instant round-trips to the exact canonical string, byte-for-byte.
    const fixed = new Date("2026-09-01T10:35:34.123Z");
    const j = new IronMcpEntry({ id: "x", namespace: "ns", pid: 9, startedAt: fixed }).toJSON();
    expect(j.started_at).toBe("2026-09-01T10:35:34.123Z");
  });

  it("discover's prune is PERSISTED: a FRESH registry instance re-reading disk sees the dead entry gone (#10)", async () => {
    // Not just an in-memory re-prune — write the dead entry, prune via one instance, then open a
    // BRAND-NEW registry (that always reports pids alive) and confirm the dead entry is truly gone
    // from registry.json on disk.
    const writer = new IronMcpRegistry({ dir, isPidAlive: () => true });
    await writer.register(new IronMcpEntry({ id: "live", namespace: "t", pid: 1 }));
    await writer.register(new IronMcpEntry({ id: "dead", namespace: "t", pid: 2 }));
    const pruner = new IronMcpRegistry({ dir, isPidAlive: (pid) => pid !== 2 });
    await pruner.discover(); // prunes "dead" and must rewrite the file
    // A fresh reader that considers EVERY pid alive would still surface "dead" if the rewrite was
    // skipped. It does not -> the prune reached disk.
    const fresh = new IronMcpRegistry({ dir, isPidAlive: () => true });
    expect(new Set((await fresh.discover()).map((e) => e.id))).toEqual(new Set(["live"]));
    const onDisk = JSON.parse(await fs.readFile(join(dir, "registry.json"), "utf8"));
    expect(Object.keys(onDisk)).toEqual(["live"]);
  });

  it("a corrupt registry.json starts fresh rather than crashing", async () => {
    await fs.mkdir(dir, { recursive: true });
    await fs.writeFile(join(dir, "registry.json"), "{ this is not json ]]", "utf8");
    const reg = new IronMcpRegistry({ dir, isPidAlive: () => true });
    // discover does not throw; it treats the garbage as empty
    expect(await reg.discover()).toEqual([]);
    // and register still lands over the top of the corruption
    await reg.register(new IronMcpEntry({ id: "a", namespace: "t", pid: 1 }));
    expect((await reg.discover()).map((e) => e.id)).toEqual(["a"]);
  });

  it("a whitespace-only registry.json is treated as empty (the trim -> {} branch)", async () => {
    await fs.mkdir(dir, { recursive: true });
    await fs.writeFile(join(dir, "registry.json"), "   \n\t  ", "utf8");
    const reg = new IronMcpRegistry({ dir, isPidAlive: () => true });
    expect(await reg.discover()).toEqual([]);
    await reg.register(new IronMcpEntry({ id: "b", namespace: "t", pid: 1 }));
    expect((await reg.discover()).map((e) => e.id)).toEqual(["b"]);
  });

  it("a non-object top-level (a JSON array) starts fresh, does not iterate garbage keys", async () => {
    await fs.mkdir(dir, { recursive: true });
    await fs.writeFile(join(dir, "registry.json"), "[1, 2, 3]", "utf8");
    const reg = new IronMcpRegistry({ dir, isPidAlive: () => true });
    expect(await reg.discover()).toEqual([]);
  });

  it("register on a corrupt file recovers (register's read() also fails open)", async () => {
    await fs.mkdir(dir, { recursive: true });
    await fs.writeFile(join(dir, "registry.json"), "\0\0not-json", "utf8");
    const reg = new IronMcpRegistry({ dir, isPidAlive: () => true });
    await reg.register(new IronMcpEntry({ id: "z", namespace: "t", pid: 1 }));
    const onDisk = JSON.parse(await fs.readFile(join(dir, "registry.json"), "utf8"));
    expect(Object.keys(onDisk)).toEqual(["z"]);
  });

  it("a LIVE lock held past lockTimeoutMs is given up on (proceed best-effort, NOT stolen)", async () => {
    // A fresh (non-stale) lock that a still-live holder keeps: the deadline must break the wait and
    // proceed best-effort, rather than stealing the lock (that only happens past staleLockAfterMs).
    const lock = join(dir, "registry.json.lock");
    await fs.mkdir(dir, { recursive: true });
    await fs.writeFile(lock, ""); // mtime = now, well within staleLockAfter
    const reg = new IronMcpRegistry({
      dir,
      isPidAlive: () => true,
      lockTimeoutMs: 40, // give up quickly
      staleLockAfterMs: 60_000, // never treat this lock as stale
    });
    const t0 = Date.now();
    await reg.register(new IronMcpEntry({ id: "a", namespace: "t", pid: 1 }));
    // it proceeded (write landed) after waiting ~lockTimeoutMs, and did NOT remove the live lock
    expect((await reg.discover()).map((e) => e.id)).toEqual(["a"]);
    expect(Date.now() - t0).toBeGreaterThanOrEqual(30);
    await expect(fs.stat(lock)).resolves.toBeTruthy(); // the live holder's lock is left intact
  });

  it("the DEFAULT pid-liveness (real process.kill) sees this process alive and a bogus pid dead", async () => {
    // No injected isPidAlive -> exercises pidAliveDefault. Our own pid is alive; a huge unused pid
    // yields ESRCH -> dead and is pruned.
    const reg = new IronMcpRegistry({ dir }); // real pidAliveDefault
    await reg.register(new IronMcpEntry({ id: "self", namespace: "t", pid: process.pid }));
    await reg.register(new IronMcpEntry({ id: "ghost", namespace: "t", pid: 2_000_000_000 }));
    expect(new Set((await reg.discover()).map((e) => e.id))).toEqual(new Set(["self"]));
  });

  it("fromJSON READS cross-kit timestamps robustly (Dart microseconds, Python +00:00, unparseable)", () => {
    // Dart-style microsecond precision — parseable by Date, kept.
    const dartMicro = IronMcpEntry.fromJSON({
      id: "d",
      namespace: "t",
      pid: 1,
      started_at: "2026-09-01T10:35:34.123456Z",
    });
    expect(Number.isNaN(dartMicro.startedAt.getTime())).toBe(false);

    // Python-style +00:00 offset — parseable by Date, kept.
    const pyOffset = IronMcpEntry.fromJSON({
      id: "p",
      namespace: "t",
      pid: 1,
      started_at: "2026-09-01T10:35:34.123456+00:00",
    });
    expect(Number.isNaN(pyOffset.startedAt.getTime())).toBe(false);

    // Unparseable string -> the Number.isNaN fallback to new Date() (a valid instant, never NaN).
    const junk = IronMcpEntry.fromJSON({ id: "j", namespace: "t", pid: 1, started_at: "not-a-date" });
    expect(Number.isNaN(junk.startedAt.getTime())).toBe(false);

    // Non-string started_at (a number) -> typeof guard falls to new Date(), still valid.
    const nonString = IronMcpEntry.fromJSON({ id: "n", namespace: "t", pid: 1, started_at: 12345 as unknown as string });
    expect(Number.isNaN(nonString.startedAt.getTime())).toBe(false);
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
