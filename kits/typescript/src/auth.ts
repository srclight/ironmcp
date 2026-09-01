// Fail-closed bearer check. No configured token means refuse everything (never a default
// that serves without a credential); the comparison is constant-time to avoid a timing oracle.
import { timingSafeEqual } from "node:crypto";

export function bearerOk(header: string | undefined, token: string): boolean {
  if (!token) return false; // fail closed: an unset token authorises nothing
  if (!header || !header.startsWith("Bearer ")) return false;
  const got = Buffer.from(header.slice(7));
  const want = Buffer.from(token);
  return got.length === want.length && timingSafeEqual(got, want);
}
