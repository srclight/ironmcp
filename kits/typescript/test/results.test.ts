import { describe, it, expect } from "vitest";
import { Results, type ImageBlock, type AudioBlock, type TextBlock } from "../src/results.js";

describe("Results", () => {
  it("json wraps a map as pretty JSON success text", () => {
    const r = Results.json({ a: 1 });
    expect(r.isError).toBeFalsy();
    expect((r.content[0] as TextBlock).text).toContain('"a": 1');
  });

  it("error sets isError:true", () => {
    const r = Results.error("nope");
    expect(r.isError).toBe(true);
    expect((r.content[0] as TextBlock).text).toBe("nope");
  });

  it("image REJECTS <=8 bytes (WSLg empty-capture trap, invariant #8)", () => {
    const r = Results.image([1, 2, 3]);
    expect(r.isError).toBe(true);
    expect((r.content[0] as TextBlock).text).toContain("empty or truncated image");
  });

  it("image REJECTS exactly 8 bytes (boundary is <=)", () => {
    const r = Results.image(new Uint8Array(8));
    expect(r.isError).toBe(true);
  });

  it("image ACCEPTS exactly 9 bytes — MIN_BYTES+1, the smallest payload that must pass (off-by-one guard)", () => {
    // 8 rejected (above) and 9 accepted here pin the EXACT `<=` boundary: a `<` slip would accept 8,
    // a `<=`-off-by-one on the accept side would reject 9. Both edges are now nailed down.
    const bytes = Uint8Array.from({ length: 9 }, (_, i) => i + 1);
    const r = Results.image(bytes);
    expect(r.isError).toBeFalsy();
    const img = r.content[0] as ImageBlock;
    expect(img.type).toBe("image");
    expect([...Buffer.from(img.data, "base64")]).toEqual([...bytes]);
  });

  it("audio ACCEPTS exactly 9 bytes too (same boundary on the non-PNG path)", () => {
    const r = Results.audio(new Uint8Array(9));
    expect(r.isError).toBeFalsy();
    expect((r.content[0] as AudioBlock).type).toBe("audio");
  });

  it("image base64-encodes real bytes byte-safely (round-trips exactly)", () => {
    const bytes = Uint8Array.from({ length: 64 }, (_, i) => i);
    const r = Results.image(bytes, "image/png");
    expect(r.isError).toBeFalsy();
    const img = r.content[0] as ImageBlock;
    expect(img.type).toBe("image");
    expect(img.mimeType).toBe("image/png");
    expect([...Buffer.from(img.data, "base64")]).toEqual([...bytes]);
  });

  it("audio covers non-PNG binary (iCE speaks) and round-trips", () => {
    const bytes = Uint8Array.from({ length: 32 }, (_, i) => 255 - i);
    const r = Results.audio(bytes, "audio/wav");
    expect(r.isError).toBeFalsy();
    const a = r.content[0] as AudioBlock;
    expect(a.type).toBe("audio");
    expect(a.mimeType).toBe("audio/wav");
    expect([...Buffer.from(a.data, "base64")]).toEqual([...bytes]);
  });

  it("audio also guards the empty capture", () => {
    expect(Results.audio([]).isError).toBe(true);
  });

  it("truncatedText marks how many chars were dropped", () => {
    const long = "x".repeat(100);
    const t = (Results.truncatedText(long, 10).content[0] as TextBlock).text;
    expect(t).toContain("[truncated 90 chars]");
    expect(t.length).toBeLessThan(long.length);
  });

  it("truncatedText leaves short text intact", () => {
    expect((Results.truncatedText("hi", 10).content[0] as TextBlock).text).toBe("hi");
  });
});
