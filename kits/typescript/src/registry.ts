// Self-discovery of ironmcp servers. File-backed, cross-language JSON (snake_case), so a Dart
// iCE, a Python *light server, and a Node scarlight all read and write the SAME discovery fabric.
//
// FORMAT — byte-compatible with kits/dart/lib/src/registry.dart (the estate-wide reference):
//   * path   = XDG dir ($XDG_RUNTIME_DIR else $XDG_STATE_HOME else ~/.local/state) + /ironmcp/
//   * file   = registry.json, a flat JSON object keyed by ENTRY ID -> entry object
//              (this MATCHES the Dart reference `map[entry.id] = entry.toJson()`; namespace is a
//              field ON each entry, not a nesting level — see note in the port report)
//   * entry  = { id, namespace, pid, host?, port?, transport?, version?, code_sha?,
//                capabilities, started_at }   — NO tool list (a consumer enumerates via
//                tools/list; loqu8 invariant #3: the count that drifted from 6 to 66)
//   * lock   = registry.json.lock, created atomically with O_EXCL (fs open flag "wx"),
//              stolen after ~30s if stale, around every read-modify-write (invariant #9)
//   * discover() prunes entries whose pid is dead and rewrites the file (lazy GC, invariant #10)
import { promises as fs } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

export type IronMcpEntryInput = {
  id: string;
  namespace: string;
  pid: number;
  host?: string;
  port?: number;
  transport?: string;
  version?: string;
  codeSha?: string;
  capabilities?: Record<string, unknown>;
  startedAt?: Date;
};

/** A live ironmcp server's registration. Language-neutral JSON (snake_case). Deliberately carries
 *  no hand-kept tool list — a consumer enumerates a server's tools via tools/list on its port. */
export class IronMcpEntry {
  readonly id: string;
  readonly namespace: string;
  readonly pid: number;
  readonly host?: string;
  readonly port?: number;
  readonly transport?: string;
  readonly version?: string;
  readonly codeSha?: string;
  readonly capabilities: Record<string, unknown>;
  readonly startedAt: Date;

  constructor(input: IronMcpEntryInput) {
    this.id = input.id;
    this.namespace = input.namespace;
    this.pid = input.pid;
    this.host = input.host;
    this.port = input.port;
    this.transport = input.transport;
    this.version = input.version;
    this.codeSha = input.codeSha;
    this.capabilities = input.capabilities ?? {};
    this.startedAt = input.startedAt ?? new Date();
  }

  toJSON(): Record<string, unknown> {
    const j: Record<string, unknown> = { id: this.id, namespace: this.namespace, pid: this.pid };
    if (this.host != null) j.host = this.host;
    if (this.port != null) j.port = this.port;
    if (this.transport != null) j.transport = this.transport;
    if (this.version != null) j.version = this.version;
    if (this.codeSha != null) j.code_sha = this.codeSha;
    j.capabilities = this.capabilities;
    j.started_at = this.startedAt.toISOString(); // ISO-8601 UTC (Date.toISOString is always Z)
    return j;
  }

  static fromJSON(j: Record<string, unknown>): IronMcpEntry {
    const started = typeof j.started_at === "string" ? new Date(j.started_at) : new Date();
    return new IronMcpEntry({
      id: j.id as string,
      namespace: j.namespace as string,
      pid: j.pid as number,
      host: (j.host as string | undefined) ?? undefined,
      port: (j.port as number | undefined) ?? undefined,
      transport: (j.transport as string | undefined) ?? undefined,
      version: (j.version as string | undefined) ?? undefined,
      codeSha: (j.code_sha as string | undefined) ?? undefined,
      capabilities: (j.capabilities as Record<string, unknown> | undefined) ?? {},
      startedAt: Number.isNaN(started.getTime()) ? new Date() : started,
    });
  }
}

function defaultDir(): string {
  const env = process.env;
  const base =
    env.XDG_RUNTIME_DIR ||
    env.XDG_STATE_HOME ||
    join(env.HOME || homedir() || ".", ".local", "state");
  return join(base, "ironmcp");
}

function pidAliveDefault(pid: number): boolean {
  try {
    // process.kill(pid, 0) probes existence without signalling. ESRCH => dead; EPERM => alive but
    // not ours (still alive). Any other error: fail open — never prune a live entry we cannot
    // verify (mirrors the Dart default).
    process.kill(pid, 0);
    return true;
  } catch (e) {
    const code = (e as NodeJS.ErrnoException).code;
    if (code === "ESRCH") return false;
    return true; // EPERM and everything else: treat as alive
  }
}

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

export type IronMcpRegistryOpts = {
  dir?: string;
  isPidAlive?: (pid: number) => boolean;
  lockTimeoutMs?: number;
  staleLockAfterMs?: number;
};

export class IronMcpRegistry {
  private readonly dir: string;
  private readonly isPidAlive: (pid: number) => boolean;
  private readonly lockTimeoutMs: number;
  private readonly staleLockAfterMs: number;

  constructor(opts: IronMcpRegistryOpts = {}) {
    this.dir = opts.dir ?? defaultDir();
    this.isPidAlive = opts.isPidAlive ?? pidAliveDefault;
    this.lockTimeoutMs = opts.lockTimeoutMs ?? 3000;
    this.staleLockAfterMs = opts.staleLockAfterMs ?? 30000;
  }

  private get file(): string {
    return join(this.dir, "registry.json");
  }

  private get lockFile(): string {
    return join(this.dir, "registry.json.lock");
  }

  async register(entry: IronMcpEntry): Promise<void> {
    await this.withLock(async () => {
      const map = await this.read();
      map[entry.id] = entry.toJSON();
      await this.write(map);
    });
  }

  async unregister(id: string): Promise<void> {
    await this.withLock(async () => {
      const map = await this.read();
      delete map[id];
      await this.write(map);
    });
  }

  /** Live servers, pruning any whose pid is dead (and rewriting the file if it pruned). A
   *  hard-killed process is cleaned up lazily on the next reader's scan, since its own unregister
   *  never ran (invariant #10). */
  async discover(): Promise<IronMcpEntry[]> {
    const live: IronMcpEntry[] = [];
    await this.withLock(async () => {
      const map = await this.read();
      let pruned = false;
      for (const key of Object.keys(map)) {
        const e = IronMcpEntry.fromJSON(map[key] as Record<string, unknown>);
        if (this.isPidAlive(e.pid)) {
          live.push(e);
        } else {
          delete map[key];
          pruned = true;
        }
      }
      if (pruned) await this.write(map);
    });
    return live;
  }

  private async read(): Promise<Record<string, unknown>> {
    try {
      const txt = await fs.readFile(this.file, "utf8");
      if (txt.trim() === "") return {};
      const parsed = JSON.parse(txt);
      return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : {};
    } catch {
      return {}; // missing/corrupt/unreadable: start fresh rather than crash
    }
  }

  private async write(map: Record<string, unknown>): Promise<void> {
    await fs.mkdir(this.dir, { recursive: true });
    const tmp = `${this.file}.tmp.${process.pid}.${Date.now()}${Math.random().toString(36).slice(2)}`;
    await fs.writeFile(tmp, JSON.stringify(map, null, 2), "utf8");
    await fs.rename(tmp, this.file); // atomic on the same filesystem
  }

  private async withLock(body: () => Promise<void>): Promise<void> {
    await fs.mkdir(this.dir, { recursive: true });
    const deadline = Date.now() + this.lockTimeoutMs;
    let acquired = false;
    for (;;) {
      try {
        // "wx" = O_CREAT | O_EXCL | O_WRONLY — the atomic create primitive (Node's O_EXCL).
        const fh = await fs.open(this.lockFile, "wx");
        await fh.close();
        acquired = true;
        break;
      } catch (e) {
        const code = (e as NodeJS.ErrnoException).code;
        if (code !== "EEXIST") {
          // Cannot even attempt the lock (e.g. permission). Proceed best-effort, like Dart.
          break;
        }
        // A crashed holder can leave a stale lock — steal it past staleLockAfter.
        try {
          const st = await fs.stat(this.lockFile);
          if (Date.now() - st.mtimeMs > this.staleLockAfterMs) {
            await fs.rm(this.lockFile, { force: true });
            continue;
          }
        } catch {
          /* lock vanished between open and stat — retry the create */
        }
        if (Date.now() > deadline) break; // proceed best-effort
        await sleep(5);
      }
    }
    try {
      await body();
    } finally {
      if (acquired) {
        try {
          await fs.rm(this.lockFile, { force: true });
        } catch {
          /* best-effort */
        }
      }
    }
  }
}
