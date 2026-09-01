# scripts/ — repo automation

## `split-mirror.sh` — monorepo kit → standalone registry mirror

Some package registries index a repository by its **root** manifest and cannot see a
package that lives in a monorepo subdirectory. Packagist is the clearest case: it reads
`composer.json` at the repo root, so our PHP kit at `kits/php/` is invisible to it. The
standard answer is a **subtree split**: a separate, read-only mirror repo whose root *is*
the package.

`split-mirror.sh` assembles that mirror deterministically and (in push mode) commits,
tags, and pushes it. It is generic — everything kit-specific lives in `<kit>/.mirror.conf`.

### How the mirror tree is assembled

From **git-tracked files only** (so each kit's own `.gitignore` — `vendor/`, lockfiles,
caches — is honoured for free):

1. the kit's tracked files → mirror root, **except** `README.md`, `.mirror.conf`, and the
   mirror README (those are monorepo-only meta);
2. the kit's mirror README (`MIRROR_README`) → `README.md` at the mirror root (a mirror
   has standalone links; the kit's in-repo README has monorepo-relative ones);
3. each `VENDOR_DIRS` entry (e.g. `conformance/`, `spec/`) → same relative path, so the
   mirror's test suite runs standalone;
4. each `ROOT_FILES` entry (e.g. `LICENSE`) → mirror root.

### Usage

```sh
# Local verification — assemble and list the tree, no git, no network:
scripts/split-mirror.sh kits/php --version 0.1.0 --dry-run --stage /tmp/stage
# then diff against the live mirror, or run its test suite from /tmp/stage.

# Push mode (what CI runs on a php-* tag): assemble + commit + tag + push the mirror.
MIRROR_TOKEN=<pat> scripts/split-mirror.sh kits/php            # version from the tag on HEAD
MIRROR_TOKEN=<pat> scripts/split-mirror.sh kits/php --version 0.1.1
```

Version mapping: the monorepo tag `php-0.1.0` (prefix from `TAG_PREFIX`) becomes the mirror
tag `0.1.0` — the plain semver Composer/Packagist reads. Existing mirror tags are treated as
**immutable**: the script refuses to move one (Packagist rejects re-publishing a version).

### Automation

`.github/workflows/split-mirror-php.yml` runs this on every `php-*` tag push (and via
`workflow_dispatch` with a version input). Packagist's own GitHub hook on the mirror repo
then picks up the new tag. dev-master refresh on every `master` commit is intentionally
**off** (low-noise; releases are what Packagist needs) — add `master` to the workflow's
`on.push.tags`/`branches` if you want it.

### One-time setup (repo admin)

- **`MIRROR_SYNC_TOKEN`** repo secret — a fine-grained PAT with **Contents: read/write on
  the mirror repo only** (least privilege). SSH deploy-key alternative: set `MIRROR_PUSH_URL`
  to an `git@github.com:…` remote instead of relying on `MIRROR_TOKEN`.
- **Packagist GitHub hook** on the mirror repo (Packagist → the package → "not auto-updated"
  → set up the hook), so a pushed tag auto-updates the package. If you skip this, set the
  optional `PACKAGIST_USERNAME` + `PACKAGIST_TOKEN` secrets and the script pings the update
  API directly.

### Adding a mirror for a future kit

No code change. Drop a `<kit>/.mirror.conf` (copy `kits/php/.mirror.conf`, adjust
`MIRROR_REPO` / `VENDOR_DIRS` / `TAG_PREFIX` / `MIRROR_README`), write that kit's mirror
README, create the mirror repo once, and add a workflow mirroring
`split-mirror-php.yml` with the kit's tag prefix. This is the generic split-mirror
infrastructure any monorepo-subdir kit needs (Go modules in a workspace subdir, Rust
workspace crates, etc.) — see the playbook in the Vault (`Cross-Platform-Kit-Playbook`, §5).
