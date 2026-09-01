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
  it("state 2 (by design): an OBJECT-valued additionalProperties enforces closed (only `true` opts open)", () => {
    // Only additionalProperties === true is the documented opt-out. An object-valued
    // additionalProperties (e.g. a zod catchall/record emitting {type:'string'}) is NOT `true`,
    // so ironmcp treats the tool as enforced and refuses undeclared extras — and stampClosed
    // rewrites the advertised schema to additionalProperties:false. This test pins that intended
    // behaviour so a future change to the opt-out predicate is a visible break, not a silent one.
    const objAdd = { type: "object", properties: { a: {} }, additionalProperties: { type: "string" } } as any;
    expect(checkUnknownArgs(objAdd, { a: 1, x: 2 }).ok).toBe(false); // extra refused
    expect(checkUnknownArgs(objAdd, { a: 1 }).ok).toBe(true); // declared arg accepted
    expect(stampClosed(objAdd)).toMatchObject({ additionalProperties: false }); // narrowed to closed
  });
  it("state 1: MALFORMED properties (a string) is UNINTROSPECTABLE -> permissive, never refuse-all", () => {
    // `properties` present but not a map: we cannot read the accepted set, so we must fail OPEN.
    // A naive Object.keys("abc") would yield ["0","1","2"] and wrongly refuse every real arg.
    const bad = { type: "object", properties: "not-an-object" } as any;
    expect(checkUnknownArgs(bad, { a: 1, b: 2 }).ok).toBe(true);
  });
  it("state 1: MALFORMED properties (a list) is UNINTROSPECTABLE -> permissive", () => {
    const bad = { type: "object", properties: ["a", "b"] } as any;
    expect(checkUnknownArgs(bad, { whatever: 1 }).ok).toBe(true);
    // and stampClosed leaves an unintrospectable schema alone (never fabricates a closed contract)
    expect(stampClosed(bad)).toEqual(bad);
  });
  it("state 2: args=undefined against an enforced schema is treated as no args (the `args ?? {}` guard) -> ok", () => {
    expect(checkUnknownArgs(withProps, undefined).ok).toBe(true);
    expect(checkUnknownArgs(zeroArg, undefined).ok).toBe(true);
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
