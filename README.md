# ironmcp

MCP servers that refuse unknown arguments instead of silently dropping them — advertisement == runtime.

Most MCP SDKs validate a tool call against its declared parameters and **silently drop** any
argument that was not declared. One added letter (`project` → `projects`) yields a confident
answer to a question nobody asked, with no way for the caller to learn their constraint was
ignored. ironmcp makes the server **refuse** the unknown argument with a bounded, recoverable
message, and **advertise exactly what it enforces** on every tool.

The contract lives in [`spec/`](spec/) and is executable as the language-neutral corpus in
[`conformance/`](conformance/). Each language kit implements that one contract natively on its
own MCP SDK and passes that one corpus — the way POSIX is a single specification with a
conformance suite and many native libraries, not one library ported everywhere.

## Before and after

```python
# Without ironmcp: search({"query": "x", "projet": "typo"}) drops `projet`, runs search("x"),
# and returns a confident wrong answer.
from ironmcp import strict_server
app = strict_server(name="search", version="1.0.0")
# With ironmcp the same call is refused:
#   unknown argument(s): projet. Tool 'search' accepts: query. Nothing was executed ...
```

## Read next

- **[AGENTS.md](AGENTS.md)** — the fast path for an AI agent: harden, serve, and prove conformance in copy-paste blocks.
- **[ROADMAP.md](ROADMAP.md)** — the kits, what has landed, what is next.
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — how to contribute, including the recipe for adding a language kit.
- **[spec/strict-args.md](spec/strict-args.md)** — the rule and the refusal message.
- **[conformance/](conformance/)** — the corpus that makes "same guarantee, every language" provable.

## Kits

| Kit | Package | Registry | Location |
|-----|---------|----------|----------|
| Python | `ironmcp` | PyPI | [`kits/python/`](kits/python/) |
| TypeScript | `ironmcp` | npm | [`kits/typescript/`](kits/typescript/) |

PHP is next; see [ROADMAP.md](ROADMAP.md). A kit conforms when a server built with its strict
layer passes every case in [`conformance/cases/`](conformance/cases/) — and every kit also
proves the bare server is refused, because a corpus never watched to FAIL is theatre.

## Harden, deploy, prove

```python
from ironmcp import strict_server, serve_http, aassert_enforces_v2
app = strict_server(name="search", version="1.0.0")     # refuse unknown args, advertise closed
serve_http(app, token="<secret>", port=8080)            # bearer-guarded /mcp + open /healthz
await aassert_enforces_v2(app)                           # prove every tool: advertise == runtime
```

The TypeScript kit mirrors this (`strictServer` / `serveHttp` / `assertEnforces`); see
[kits/typescript/README.md](kits/typescript/README.md).

## Layout

```
spec/                 the contract (language-agnostic)
conformance/cases/    the corpus (one, owned by no language)
kits/<language>/      one native kit per language, each passing the corpus
```
