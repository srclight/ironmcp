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
  it("rejects an EQUAL-LENGTH wrong token (exercises the timingSafeEqual false branch, not the length short-circuit)", () => {
    // Same length as "s3cret-token" (12 chars) but wrong — a stub that returned true for any
    // equal-length input would pass every OTHER negative test, which all differ in length. This
    // is the one that forces the constant-time compare itself to return false.
    const wrong = "X3cret-token";
    expect(wrong.length).toBe(token.length);
    expect(bearerOk(`Bearer ${wrong}`, token)).toBe(false);
    // and a same-length token differing only in the LAST byte
    expect(bearerOk("Bearer s3cret-tokeX", "s3cret-tokeY")).toBe(false);
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
  it("parses a bracketed IPv6 literal, stripping the port only after the closing ']'", () => {
    // A naive host.split(":")[0] turns "[::1]:8080" into "[" (the first colon is inside the
    // address), so a bracketed IPv6 client would be wrongly refused. The port must be stripped
    // only after the closing bracket.
    const v6 = new HostGuard(["[::1]"]);
    expect(v6.accepts("[::1]")).toBe(true); // exact
    expect(v6.accepts("[::1]:8080")).toBe(true); // port stripped after ']'
    expect(v6.accepts("[::2]:8080")).toBe(false); // a different v6 host is still refused
    expect(v6.accepts("[")).toBe(false); // the naive-split artefact must NOT match
    // and a full v6 literal in the allowlist matches with a port too
    const full = new HostGuard(["[2001:db8::1]"]);
    expect(full.accepts("[2001:db8::1]")).toBe(true);
    expect(full.accepts("[2001:db8::1]:18888")).toBe(true);
  });
  it("host matching is CASE-INSENSITIVE (HTTP Host is case-insensitive, RFC 7230)", () => {
    // "Localhost" / "LOCALHOST" must match a "localhost" allowlist entry, and a mixed-case
    // allowlist entry must match a lower-case incoming host — both sides fold to lower case.
    expect(guard.accepts("Localhost")).toBe(true);
    expect(guard.accepts("LOCALHOST:8080")).toBe(true);
    expect(guard.accepts("Wasabi.Local:18888")).toBe(true);
    const mixed = new HostGuard(["MyHost.Local", "127.0.0.1"]);
    expect(mixed.accepts("myhost.local")).toBe(true);
    expect(mixed.accepts("MYHOST.LOCAL:9000")).toBe(true);
    // a genuinely foreign host is still refused regardless of case
    expect(guard.accepts("EVIL.example.com")).toBe(false);
  });
});
