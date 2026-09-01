import { describe, it, expect } from "vitest";
import { bearerOk, HostGuard } from "../src/auth.js";

describe("bearerOk (constant-time, fail closed — invariant #4)", () => {
  const token = "s3cret-token";
  it("accepts the exact Bearer token", () => {
    expect(bearerOk("Bearer s3cret-token", token)).toBe(true);
  });
  it("rejects a wrong token", () => {
    expect(bearerOk("Bearer nope", token)).toBe(false);
  });
  it("rejects a missing/empty/malformed header (401 material)", () => {
    expect(bearerOk(undefined, token)).toBe(false);
    expect(bearerOk("", token)).toBe(false);
    expect(bearerOk("s3cret-token", token)).toBe(false); // no Bearer prefix
    expect(bearerOk("Bearer ", token)).toBe(false); // empty presented token
  });
  it("an empty EXPECTED token authorises nothing (fail closed)", () => {
    expect(bearerOk("Bearer ", "")).toBe(false);
    expect(bearerOk("Bearer anything", "")).toBe(false);
  });
  it("a token that is a prefix of the secret is rejected (length-checked)", () => {
    expect(bearerOk("Bearer s3cret", token)).toBe(false);
  });
});

describe("HostGuard (DNS-rebinding, default ON — invariant #4)", () => {
  const guard = new HostGuard(["localhost", "127.0.0.1", "wasabi.local"]);
  it("accepts an allowed host, with or without a port", () => {
    expect(guard.accepts("localhost")).toBe(true);
    expect(guard.accepts("localhost:8080")).toBe(true);
    expect(guard.accepts("wasabi.local:18888")).toBe(true);
  });
  it("rejects a rebinding attacker host and a null/empty host", () => {
    expect(guard.accepts("evil.example.com")).toBe(false);
    expect(guard.accepts("evil.example.com:8080")).toBe(false);
    expect(guard.accepts(null)).toBe(false);
    expect(guard.accepts(undefined)).toBe(false);
    expect(guard.accepts("")).toBe(false);
  });
  it("allowPortlessMatch:false requires an exact host:port match", () => {
    const strict = new HostGuard(["localhost:8080"], { allowPortlessMatch: false });
    expect(strict.accepts("localhost:8080")).toBe(true);
    expect(strict.accepts("localhost")).toBe(false);
  });
});
