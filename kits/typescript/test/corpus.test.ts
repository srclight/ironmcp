import { describe, it, expect } from "vitest";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { buildBareServer } from "./fixtures.js";
import { strictServer } from "../src/register.js";
import { assertEnforces } from "../src/corpus.js";

// test/ -> typescript -> kits -> repo root, where the language-neutral corpus lives.
const CASES = resolve(dirname(fileURLToPath(import.meta.url)), "../../../conformance/cases");

describe("conformance corpus (the shared, language-neutral gate)", () => {
  it("a strictServer passes every case", async () => {
    const n = await assertEnforces(strictServer(buildBareServer()), CASES);
    expect(n).toBeGreaterThanOrEqual(4);
  });
  it("a BARE server FAILS the corpus (a corpus never watched to fail is theatre)", async () => {
    await expect(assertEnforces(buildBareServer(), CASES)).rejects.toThrow();
  });
});
