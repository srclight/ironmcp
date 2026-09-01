// Read the language-neutral corpus and drive it through a real client<->server session.
// The cases live at the repo root (conformance/cases), owned by no language; this runner is
// the TypeScript proof that a strict server passes them and a bare one does not.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";

export type CorpusResult = { id: string; pass: boolean; detail?: string };

type Case = {
  id: string;
  tool: string;
  arguments: Record<string, unknown>;
  expect: "refuse" | "accept";
  expect_message_contains?: string[];
  expect_message_excludes?: string[];
  expect_structured?: Record<string, string[]>;
};

export function loadCases(casesDir: string): Case[] {
  return readdirSync(casesDir)
    .filter((f) => f.endsWith(".json"))
    .sort()
    .map((f) => JSON.parse(readFileSync(join(casesDir, f), "utf8")) as Case);
}

/** Run every case against a server through a session; throw with detail if any fails.
 *  Returns the number of cases passed. */
export async function assertEnforces(server: any, casesDir: string): Promise<number> {
  const cases = loadCases(casesDir);
  const [ct, st] = InMemoryTransport.createLinkedPair();
  await server.connect(st);
  const client = new Client({ name: "corpus", version: "0" });
  await client.connect(ct);
  const failures: string[] = [];
  try {
    for (const c of cases) {
      const r: any = await client.callTool({ name: c.tool, arguments: c.arguments });
      const isErr = r.isError === true;
      const text = (r.content ?? []).map((x: any) => x.text ?? "").join(" ");
      if (c.expect === "refuse" && !isErr) failures.push(`${c.id}: expected refuse, got accept`);
      if (c.expect === "accept" && isErr) failures.push(`${c.id}: expected accept, got refuse (${text})`);
      for (const s of c.expect_message_contains ?? [])
        if (!text.includes(s)) failures.push(`${c.id}: message missing '${s}'`);
      for (const s of c.expect_message_excludes ?? [])
        if (text.includes(s)) failures.push(`${c.id}: message leaked '${s}'`);
      // expect_structured: the refusal must carry structuredContent.ironmcp whose named
      // fields CONTAIN the expected keys (machine-readable, not just prose).
      if (c.expect_structured) {
        const iron = (r.structuredContent as any)?.ironmcp;
        for (const [field, expected] of Object.entries(c.expect_structured)) {
          const got = iron?.[field];
          if (!Array.isArray(got) || !expected.every((k) => got.includes(k)))
            failures.push(`${c.id}: structuredContent.ironmcp.${field} missing ${JSON.stringify(expected)} (got ${JSON.stringify(got)})`);
        }
      }
    }
  } finally {
    await client.close();
    await server.close();
  }
  if (failures.length) throw new Error(`conformance failures:\n  ${failures.join("\n  ")}`);
  return cases.length;
}
