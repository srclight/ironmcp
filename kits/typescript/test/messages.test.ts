import { describe, it, expect } from "vitest";
import { unknownArgsMessage, MAX_ENUMERATED } from "../src/messages.js";

describe("unknownArgsMessage", () => {
  it("names the unknown key and the accepted set, and says nothing ran", () => {
    const m = unknownArgsMessage("echo", ["typo"], ["a", "b"]);
    expect(m).toContain("unknown argument(s): typo");
    expect(m).toContain("accepts: a, b");
    expect(m).toContain("Nothing was executed");
  });
  it("bounds enumeration at MAX_ENUMERATED then says 'and N more'", () => {
    const unknown = Array.from({ length: MAX_ENUMERATED + 5 }, (_, i) => `z${String(i).padStart(3, "0")}`);
    const m = unknownArgsMessage("echo", unknown, ["a"]);
    expect(m).toContain("and 5 more");
    expect(m).not.toContain("z014"); // the 15th key is past the cap
  });
  it("sorts the accepted set and never needs a value to build the message", () => {
    const m = unknownArgsMessage("echo", ["secret"], ["b", "a"]);
    expect(m).toContain("accepts: a, b"); // sorted
  });
  it("diagnoses an NFKC-confusable key by codepoint", () => {
    const m = unknownArgsMessage("echo", ["ａ"], ["a"]); // fullwidth a -> NFKC 'a'
    expect(m).toContain("U+FF41");
    expect(m).toContain("which IS accepted");
  });
  it("names '(no arguments)' when the accepted set is empty (a zero-arg tool refusing an extra)", () => {
    const m = unknownArgsMessage("ping", ["typo"], []);
    expect(m).toContain("accepts: (no arguments)");
    expect(m).toContain("unknown argument(s): typo");
  });
  it("ends with the reconnect hint", () => {
    const m = unknownArgsMessage("echo", ["typo"], ["a"], "check status and reconnect");
    expect(m.trimEnd()).toMatch(/check status and reconnect\.$/);
  });
});
