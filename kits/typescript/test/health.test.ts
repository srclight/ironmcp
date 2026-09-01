import { describe, it, expect } from "vitest";
import { codeSha, healthPayload } from "../src/health.js";
import { bearerOk } from "../src/auth.js";

describe("health", () => {
  it("codeSha returns a string and never throws", () => {
    expect(typeof codeSha()).toBe("string");
  });
  it("healthPayload carries ok + version + codeSha + extra", () => {
    const h = healthPayload({ revision: "abc" });
    expect(h.ok).toBe(true);
    expect(typeof h.codeSha).toBe("string");
    expect(h.revision).toBe("abc");
  });
});

describe("bearerOk (fail closed)", () => {
  it("empty configured token -> always false", () => {
    expect(bearerOk("Bearer x", "")).toBe(false);
  });
  it("missing header -> false", () => {
    expect(bearerOk(undefined, "secret")).toBe(false);
  });
  it("wrong token -> false", () => {
    expect(bearerOk("Bearer nope", "secret")).toBe(false);
  });
  it("correct token -> true", () => {
    expect(bearerOk("Bearer secret", "secret")).toBe(true);
  });
});
