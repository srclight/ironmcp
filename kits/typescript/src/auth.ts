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

/** DNS-rebinding / host-allowlist guard. Posture is ON by default: a request whose `Host` header
 *  is not in allowedHosts is rejected. loqu8 bound 0.0.0.0 with rebinding OFF while a comment
 *  falsely claimed it was on — this defaults it ON (invariant #4). Give it the hosts the server
 *  legitimately answers as (add the WSL/LAN name/IP + `localhost` when 0.0.0.0-bound, so WSL reach
 *  still works while a rebinding attacker's `Host` is refused). */
export class HostGuard {
  readonly allowedHosts: Set<string>;
  readonly allowPortlessMatch: boolean;

  constructor(allowedHosts: Iterable<string>, opts: { allowPortlessMatch?: boolean } = {}) {
    this.allowedHosts = new Set(allowedHosts);
    this.allowPortlessMatch = opts.allowPortlessMatch ?? true;
  }

  /** True iff hostHeader is allowed. A null/undefined/empty host is rejected. */
  accepts(hostHeader: string | undefined | null): boolean {
    if (!hostHeader) return false;
    if (this.allowedHosts.has(hostHeader)) return true;
    if (this.allowPortlessMatch && this.allowedHosts.has(hostHeader.split(":")[0])) return true;
    return false;
  }
}
