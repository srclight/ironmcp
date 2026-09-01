// The unknown-argument refusal message. No SDK import; pure. Byte-compatible with the
// Python kit's _messages.unknown_args_message so the guarantee reads identically in both.

export const DEFAULT_RECONNECT_HINT =
  "check the server's reported revision and reconnect the MCP";

// The error message's SIZE is bounded by the server, never by its input. A caller sending
// thousands of unknown keys must not reflect a huge error back over MCP and into a log.
// Values are NEVER echoed, only key NAMES.
export const MAX_ENUMERATED = 10;

function codepoints(s: string): string {
  return Array.from(s)
    .map((c) => "U+" + c.codePointAt(0)!.toString(16).toUpperCase().padStart(4, "0"))
    .join(" ");
}

export function unknownArgsMessage(
  name: string,
  unknown: string[],
  accepted: string[],
  reconnectHint: string = DEFAULT_RECONNECT_HINT,
): string {
  const shown = unknown.slice(0, MAX_ENUMERATED);
  const more = unknown.length - shown.length;
  const listed = shown.join(", ") + (more > 0 ? `, and ${more} more` : "");
  const accepts = accepted.length ? [...accepted].sort().join(", ") : "(no arguments)";

  // NFKC confusables: a parameter written with U+FF41 is glyph-identical to an accepted 'a'
  // in nearly every font. THE SCHEMA IS AUTHORITATIVE FOR ARGUMENT NAMES, NEVER THE SOURCE,
  // because normalisation happens between them. Diagnose by naming the codepoint.
  const normAccepted = new Map(accepted.map((a) => [a.normalize("NFKC"), a]));
  const hints: string[] = [];
  for (const k of shown) {
    const canon = k.normalize("NFKC");
    if (canon !== k && normAccepted.has(canon)) {
      hints.push(`'${k}' (${codepoints(k)}) normalises to '${normAccepted.get(canon)}', which IS accepted`);
    }
  }

  const parts = [
    `unknown argument(s): ${listed}.`,
    `Tool '${name}' accepts: ${accepts}.`,
    "Nothing was executed and no result was computed.",
  ];
  if (hints.length) parts.push("Note: " + hints.join("; ") + ".");
  parts.push(
    `If you expected these arguments to work, this server process is probably running older code than you think - ${reconnectHint}.`,
  );
  return parts.join(" ");
}
