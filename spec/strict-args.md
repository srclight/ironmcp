# strict-args — refuse unknown tool arguments

## The problem

Most MCP SDKs validate a tool call against the tool's declared parameters and **silently
drop** any argument that isn't declared, before the tool body runs. No error is raised,
and the advertised schema usually omits `additionalProperties`, so nothing at the
protocol layer flags it either. One added letter (`project` → `projects`) yields a
genuine answer to a question nobody asked, with no way for the caller to learn their
constraint was ignored. This is not a lossy call; it is a wrong one.

This is not a language problem — it has been observed in the Python and TypeScript SDKs
alike. Every MCP server must supply argument-refusal for itself.

## The rule (three states)

For an incoming tool call, inspect the tool's declared input schema:

1. **No `properties` key** → the schema is uninintrospectable. **Stay permissive** — do
   not refuse. A guard that bricks what it cannot read is worse than the bug it prevents.
2. **`properties` present** (even the empty object `{}`, as a zero-argument tool has)
   **and `additionalProperties` is not `true`** → **refuse** any argument key not in
   `properties`. *(Pins: corpus `001`, `003`.)*
3. **`additionalProperties: true`** → the author has **opted out** (a passthrough/proxy
   tool that accepts arbitrary keys — the JSON-Schema standard way to say so).
   **Honour it**; do not refuse. *(Refusing here would advertise-open-but-refuse — the
   catalog-lies-about-runtime bug, pointing the other way.)*

Refusal means the call returns as an **error result** and the tool body **never runs**.
*(Pins: corpus `001` — "Nothing was executed".)*

## The refusal message

- Name the **unknown argument key(s)** and the tool's **accepted** keys.
- **Never echo argument values** — only key names. Bound the enumerated keys (cap at 10,
  then "and N more"). A caller sending thousands of unknown keys must not reflect a large
  error back into logs. *(Pins: corpus `004`.)*
- State that nothing was executed and no result was computed.
- If argument names may differ from source by Unicode normalisation (e.g. a parameter
  written `µ` U+00B5 is advertised as `μ` U+03BC), and a refused key normalises (NFKC) to
  an accepted one, say so and name the codepoints. **The schema is authoritative for
  argument names, never the source** — normalisation happens between them.
- End with a recoverability hint: if the caller expected these arguments to work, the
  server is probably running older code than they think — reconnect / check its revision.

## Advertise what you enforce

A server that refuses at runtime must also advertise it: stamp `additionalProperties:
false` onto every listed tool schema that has `properties` and is not opted open. Refusing
while advertising a permissive schema tells agents extras are fine, so they keep sending
them. See [conformance.md](conformance.md).
