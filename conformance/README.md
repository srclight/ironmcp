# ironmcp conformance corpus

The behavioural contract of ironmcp, expressed as language-neutral JSON — owned by no
language. **A kit conforms when a server built with its strict layer passes every case.**
This is what makes "the same guarantee in every language" *provable* rather than claimed.

## Case schema

```json
{
  "id": "001-unknown-arg-refused",
  "description": "one sentence: what behaviour this pins",
  "tool": "echo",
  "arguments": { "a": "x", "typo": "ignored" },
  "expect": "refuse",
  "expect_message_contains": ["unknown argument", "Nothing was executed"],
  "expect_message_excludes": ["SENTINEL_VALUE_9f3a"]
}
```

- `expect`: `"refuse"` (the call must come back as an error result) or `"accept"` (it must not).
- `expect_structured` (optional): an object `{field: [keys]}` the refusal's machine-readable
  `structuredContent.ironmcp` must carry, each field CONTAINING the listed keys (e.g.
  `{"unknown": ["typo"], "accepted": ["a","b"]}`). Pins that a refusal is parseable, not only prose.
- `expect_message_contains` / `expect_message_excludes` (optional): substrings the refusal
  message must / must not contain. `excludes` is how we pin that argument *values* are never
  echoed back (only key *names*).

## The fixture server

Every runner builds a server, guarded by its strict layer, exposing at least:

- `echo(a: str, b: str = "default")` — a two-argument tool.
- `ping()` — a zero-argument tool (its schema has `properties: {}` — present but empty; a typo
  must still be refused, not dropped).

## How to run it (per language)

- **Python** (this repo): `ironmcp.corpus.run_corpus(server, "conformance/cases")` returns a
  `list[Result]`; a conforming server yields zero failures. See `tests/test_corpus.py`.
- **Other kits**: reimplement a runner that reads these JSON files and drives its own
  in-process server the way a real client would. Same cases, same verdicts.

## The rule

New behaviour enters ironmcp only with a case here that pins it. A guarantee with no case is
not a guarantee. A corpus never watched to FAIL against a non-conforming server is theatre —
so the Python suite also asserts these cases reject a bare (unguarded) server.
