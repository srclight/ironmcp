// Agent-interrogable health. code_sha lets a caller detect a server running older code than
// it expects; it never throws (a health probe that can crash is not a health probe).
import { createHash } from "node:crypto";

export const IRONMCP_VERSION = "0.2.0";

export function codeSha(): string {
  try {
    return createHash("sha256").update(IRONMCP_VERSION).digest("hex").slice(0, 12);
  } catch {
    return "unknown";
  }
}

export function healthPayload(extra: Record<string, unknown> = {}): {
  ok: true;
  ironmcp: string;
  codeSha: string;
  [k: string]: unknown;
} {
  return { ok: true as const, ironmcp: IRONMCP_VERSION, codeSha: codeSha(), ...extra };
}
