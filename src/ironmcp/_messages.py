"""The unknown-argument refusal message. Copied from the v1 kit's strict module and kept
free of any ``mcp`` import so it loads cleanly under ``mcp>=2`` (where FastMCP is a
tombstone). Behavior is identical to v1 and is pinned by the conformance corpus.
"""

from __future__ import annotations

import unicodedata

# The generic stale-server diagnosis, used when a server does not name its own revision
# surface. A server that HAS one supplies a better string via the ``reconnect_hint``
# constructor argument. It is DATA, never a method.
_DEFAULT_RECONNECT_HINT = "check the server's reported revision and reconnect the MCP"

# The error message's SIZE is bounded by the server, never by its input. A caller sending
# 5,000 unknown keys must not be able to reflect a 59 kB error back over MCP and into the
# log. Values are NEVER echoed, only key NAMES.
_MAX_ENUMERATED = 10


def unknown_args_message(
    name: str,
    unknown: list[str],
    accepted: set[str],
    reconnect_hint: str = _DEFAULT_RECONNECT_HINT,
) -> str:
    shown = unknown[:_MAX_ENUMERATED]
    more = len(unknown) - len(shown)
    listed = ", ".join(shown) + (f", and {more} more" if more > 0 else "")
    accepts = ", ".join(sorted(accepted)) if accepted else "(no arguments)"

    # NFKC confusables. Python normalises identifiers at PARSE time, so a parameter written
    # with U+00B5 MICRO SIGN is advertised as U+03BC GREEK MU -- two glyphs identical in
    # nearly every font. Diagnose it by naming the CODEPOINT. THE SCHEMA IS AUTHORITATIVE
    # FOR ARGUMENT NAMES, NEVER THE SOURCE, because normalisation happens between them.
    hints = []
    norm_accepted = {unicodedata.normalize("NFKC", a): a for a in accepted}
    for k in shown:
        canon = unicodedata.normalize("NFKC", k)
        if canon != k and canon in norm_accepted:
            cps = " ".join(f"U+{ord(c):04X}" for c in k)
            hints.append(f"{k!r} ({cps}) normalises to {norm_accepted[canon]!r}, which IS accepted")

    parts = [
        f"unknown argument(s): {listed}.",
        f"Tool {name!r} accepts: {accepts}.",
        "Nothing was executed and no result was computed.",
    ]
    if hints:
        parts.append("Note: " + "; ".join(hints) + ".")
    parts.append(
        "If you expected these arguments to work, this server process is probably running older "
        f"code than you think - {reconnect_hint}."
    )
    return " ".join(parts)
