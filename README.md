# ironmcp

The hardening and conformance standard for MCP servers: tool servers that **refuse unknown
arguments instead of silently dropping them**, and advertise exactly what they enforce
(advertisement == runtime).

The behavioural contract lives in [`spec/`](spec/) and is executable as the language-neutral
corpus in [`conformance/`](conformance/). Each language kit implements that one contract
natively on its own MCP SDK and passes that one corpus — the way POSIX is a single spec with
many native libraries, not one library ported everywhere.

## Kits

| Kit | Package | Registry | Location |
|-----|---------|----------|----------|
| Python | `ironmcp` | PyPI | [`kits/python/`](kits/python/) |
| TypeScript | `ironmcp` | npm | [`kits/typescript/`](kits/typescript/) |

A kit conforms when a server built with its strict layer passes every case in
[`conformance/cases/`](conformance/cases/). A corpus never watched to FAIL against an
unguarded server is theatre, so every kit also proves the bare server is refused.

## Layout

```
spec/                 the contract (language-agnostic)
conformance/cases/    the corpus (one, owned by no language)
kits/<language>/      one native kit per language, each passing the corpus
```
