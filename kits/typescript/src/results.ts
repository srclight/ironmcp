// Content/result helpers — the generic PIPING an app tool rides on. The screenshot/audio
// CAPTURE stays app-side; ironmcp owns how raw bytes become a well-formed, guarded MCP result.
// No helper echoes a caller-supplied value. Pure: no SDK import, so the core stays trivially
// testable and robust across @modelcontextprotocol/sdk versions.

export type TextBlock = { type: "text"; text: string };
export type ImageBlock = { type: "image"; data: string; mimeType: string };
export type AudioBlock = { type: "audio"; data: string; mimeType: string };
export type ContentBlock = TextBlock | ImageBlock | AudioBlock;
export type ToolResult = { content: ContentBlock[]; isError?: boolean };

/** Minimum bytes that count as real payload. A WSLg/X11 capture can exit 0 yet emit an empty
 *  (<=8-byte) file; treat that as a failure, not media (loqu8 invariant #8). */
export const MIN_BYTES = 8;

type Bytes = Uint8Array | ArrayLike<number>;

function toBuffer(bytes: Bytes): Buffer {
  return Buffer.from(bytes as Uint8Array);
}

/** Success result carrying pretty-printed JSON. */
function json(data: Record<string, unknown>): ToolResult {
  return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
}

/** Success result carrying plain text. */
function text(message: string): ToolResult {
  return { content: [{ type: "text", text: message }] };
}

/** An error result (`isError: true`) so the caller/agent sees the tool failed. */
function error(message: string): ToolResult {
  return { content: [{ type: "text", text: message }], isError: true };
}

function binary(bytes: Bytes, mimeType: string, kind: "image" | "audio"): ToolResult {
  const buf = toBuffer(bytes);
  if (buf.length <= MIN_BYTES) {
    return error(
      `empty or truncated ${kind} (${buf.length} bytes) — the capture produced no usable data`,
    );
  }
  const data = buf.toString("base64");
  return { content: [{ type: kind, data, mimeType } as ContentBlock] };
}

/** Image result, or an [error] when the bytes are missing/too small (invariant #8). */
function image(bytes: Bytes, mimeType = "image/png"): ToolResult {
  return binary(bytes, mimeType, "image");
}

/** Audio result (iCE speaks), or an [error] when empty/too small. Proves the piping is not
 *  PNG-only. */
function audio(bytes: Bytes, mimeType = "audio/wav"): ToolResult {
  return binary(bytes, mimeType, "audio");
}

/** Truncate [body] to [maxChars], appending a marker naming how many chars were dropped, so an
 *  agent never mistakes a partial payload for the whole thing. */
function truncatedText(body: string, maxChars = 20000): ToolResult {
  if (body.length <= maxChars) return text(body);
  const dropped = body.length - maxChars;
  return text(`${body.slice(0, maxChars)}\n…[truncated ${dropped} chars]`);
}

export const Results = { json, text, error, image, audio, truncatedText };
