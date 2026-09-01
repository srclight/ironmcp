import { describe, it, expect } from "vitest";
import { checkUnknownArgs, stampClosed } from "../src/strict.js";

const withProps = { type: "object", properties: { a: {}, b: {} } };
const zeroArg = { type: "object", properties: {} };

describe("checkUnknownArgs — the 3-state rule", () => {
  it("state 2: properties present, unknown key -> refuse", () => {
    const r = checkUnknownArgs(withProps, { a: 1, typo: 2 }, { toolName: "echo" });
    expect(r.ok).toBe(false);
    if (!r.ok) {
      expect(r.unknown).toEqual(["typo"]);
      expect(r.message).toContain("unknown argument");
    }
  });
  it("state 2: known keys -> ok", () => {
    expect(checkUnknownArgs(withProps, { a: 1, b: 2 }).ok).toBe(true);
  });
  it("state 2: zero-arg tool (empty properties) still refuses extras", () => {
    expect(checkUnknownArgs(zeroArg, { typo: 1 }).ok).toBe(false);
  });
  it("state 1: no properties key -> permissive (do not brick what we cannot read)", () => {
    expect(checkUnknownArgs({ type: "object" }, { whatever: 1 }).ok).toBe(true);
  });
  it("state 3: additionalProperties:true -> honour the opt-out", () => {
    expect(
      checkUnknownArgs({ type: "object", properties: { a: {} }, additionalProperties: true }, { a: 1, x: 2 }).ok,
    ).toBe(true);
  });
  it("undefined schema -> permissive", () => {
    expect(checkUnknownArgs(undefined, { x: 1 }).ok).toBe(true);
  });
});

describe("stampClosed", () => {
  it("stamps additionalProperties:false when properties present and not opted open", () => {
    expect(stampClosed(withProps)).toMatchObject({ additionalProperties: false });
  });
  it("stamps a zero-arg schema closed", () => {
    expect(stampClosed(zeroArg)).toMatchObject({ additionalProperties: false });
  });
  it("leaves an opted-open schema alone", () => {
    const open = { type: "object", properties: { a: {} }, additionalProperties: true };
    expect(stampClosed(open)).toEqual(open);
  });
  it("leaves an unintrospectable schema alone", () => {
    const bare = { type: "object" };
    expect(stampClosed(bare)).toEqual(bare);
  });
});
