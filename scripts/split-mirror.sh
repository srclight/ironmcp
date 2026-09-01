#!/usr/bin/env bash
#
# split-mirror.sh — assemble a monorepo kit into its standalone Packagist/registry
# mirror repo, then (optionally) commit + tag + push it. Generic: everything
# kit-specific lives in <kit-dir>/.mirror.conf, so a new kit's mirror is a new
# config file, not new code. See kits/php/.mirror.conf for the contract.
#
# The mirror tree is assembled from GIT-TRACKED files only, so each kit's own
# .gitignore (vendor/, lockfiles, caches) is honoured for free.
#
# Usage:
#   scripts/split-mirror.sh <kit-dir> [--version X.Y.Z] [--dry-run] [--stage DIR]
#
#   <kit-dir>       path to the kit, e.g. kits/php (must contain .mirror.conf)
#   --version       mirror semver (no prefix). If omitted, derived from the tag
#                   $TAG_PREFIX$VERSION currently pointing at HEAD.
#   --dry-run       assemble into the stage dir and print the file list; no git,
#                   no network. Used by CI and for local verification.
#   --stage DIR     staging dir (default: a mktemp dir; printed on dry-run).
#
# Push mode (no --dry-run) requires:
#   MIRROR_PUSH_URL  authenticated push URL for $MIRROR_REPO, e.g.
#                    https://x-access-token:$TOKEN@github.com/srclight/ironmcp-php.git
#                    or git@github.com:srclight/ironmcp-php.git (with an agent/deploy key).
# Optional Packagist ping after push:
#   PACKAGIST_USERNAME + PACKAGIST_TOKEN  -> POST to the update API for $PACKAGIST_PACKAGE.
#
set -euo pipefail

die() { printf 'split-mirror: %s\n' "$*" >&2; exit 1; }
log() { printf 'split-mirror: %s\n' "$*" >&2; }

KIT_DIR="" VERSION="" DRY_RUN=0 STAGE=""
[ $# -ge 1 ] || die "usage: split-mirror.sh <kit-dir> [--version X.Y.Z] [--dry-run] [--stage DIR]"
KIT_DIR="$1"; shift
while [ $# -gt 0 ]; do
  case "$1" in
    --version) VERSION="${2:?--version needs a value}"; shift 2;;
    --dry-run) DRY_RUN=1; shift;;
    --stage)   STAGE="${2:?--stage needs a dir}"; shift 2;;
    *) die "unknown arg: $1";;
  esac
done

REPO_ROOT="$(git rev-parse --show-toplevel)" || die "not inside a git repo"
cd "$REPO_ROOT"
KIT_DIR="${KIT_DIR%/}"
[ -d "$KIT_DIR" ] || die "kit dir not found: $KIT_DIR"
CONF="$KIT_DIR/.mirror.conf"
[ -f "$CONF" ] || die "no .mirror.conf in $KIT_DIR"
# shellcheck disable=SC1090
. "$CONF"
: "${MIRROR_REPO:?.mirror.conf must set MIRROR_REPO}"
: "${MIRROR_README:?.mirror.conf must set MIRROR_README}"
: "${TAG_PREFIX:?.mirror.conf must set TAG_PREFIX}"
VENDOR_DIRS="${VENDOR_DIRS:-}"; ROOT_FILES="${ROOT_FILES:-}"

# Derive VERSION from the tag on HEAD if not given.
if [ -z "$VERSION" ]; then
  for t in $(git tag --points-at HEAD 2>/dev/null || true); do
    case "$t" in "$TAG_PREFIX"*) VERSION="${t#"$TAG_PREFIX"}"; break;; esac
  done
fi

# Files under the kit that are meta-only and must NOT ship to the mirror.
# (The kit's own README.md has monorepo-relative links; the mirror gets MIRROR_README as README.md.)
kit_excluded() {
  case "$1" in
    "README.md"|".mirror.conf"|"$MIRROR_README") return 0;;
    *) return 1;;
  esac
}

[ -n "$STAGE" ] || STAGE="$(mktemp -d)"
mkdir -p "$STAGE"
# Clean any prior contents of an explicit stage dir (but never touch a .git there).
find "$STAGE" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} + 2>/dev/null || true

copy_into_stage() { # <src-relpath> <dest-relpath>
  local dest="$STAGE/$2"
  mkdir -p "$(dirname "$dest")"
  cp -p "$1" "$dest"
}

# 1) kit files (tracked) -> mirror root, minus the meta-only ones.
while IFS= read -r f; do
  rel="${f#"$KIT_DIR"/}"
  kit_excluded "$rel" && continue
  copy_into_stage "$f" "$rel"
done < <(git ls-files "$KIT_DIR")

# 2) mirror README -> README.md at the mirror root.
[ -f "$KIT_DIR/$MIRROR_README" ] || die "mirror README missing: $KIT_DIR/$MIRROR_README"
copy_into_stage "$KIT_DIR/$MIRROR_README" "README.md"

# 3) vendored root dirs (tracked) -> same relative path.
for d in $VENDOR_DIRS; do
  [ -d "$d" ] || die "vendor dir not found: $d"
  while IFS= read -r f; do copy_into_stage "$f" "$f"; done < <(git ls-files "$d")
done

# 4) root files.
for f in $ROOT_FILES; do
  [ -f "$f" ] || die "root file not found: $f"
  copy_into_stage "$f" "$f"
done

log "assembled $KIT_DIR -> mirror tree in $STAGE (version: ${VERSION:-<none>})"
( cd "$STAGE" && find . -type f ! -path './.git/*' | sed 's#^\./##' | sort )

if [ "$DRY_RUN" -eq 1 ]; then
  log "dry-run: stage=$STAGE (not committed, not pushed)"
  exit 0
fi

[ -n "$VERSION" ] || die "no --version and no ${TAG_PREFIX}* tag on HEAD; cannot tag the mirror"
# Resolve the authenticated push URL. Prefer an explicit MIRROR_PUSH_URL (e.g. an SSH
# deploy-key remote); otherwise build an HTTPS token URL from MIRROR_REPO + MIRROR_TOKEN.
if [ -z "${MIRROR_PUSH_URL:-}" ]; then
  [ -n "${MIRROR_TOKEN:-}" ] || die "push mode needs MIRROR_PUSH_URL or MIRROR_TOKEN"
  MIRROR_PUSH_URL="https://x-access-token:${MIRROR_TOKEN}@github.com/${MIRROR_REPO}.git"
fi

WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
log "cloning mirror $MIRROR_REPO ..."
git clone --quiet "$MIRROR_PUSH_URL" "$WORK/mirror" || die "clone failed"
cd "$WORK/mirror"
# CI runners have no global git identity; set a local one so commit AND annotated tag work.
git config user.name "ironmcp-bot"
git config user.email "bot@ironmcp.dev"
DEFAULT_BRANCH="$(git symbolic-ref --quiet --short HEAD || echo master)"

# Refuse to move an existing immutable version tag (Packagist rejects re-publishing it).
if git rev-parse -q --verify "refs/tags/$VERSION" >/dev/null; then
  die "mirror already has tag $VERSION — versions are immutable; bump the kit version"
fi

# Replace tracked content with the freshly assembled tree (preserve .git).
find . -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
cp -a "$STAGE"/. .
git add -A
if git diff --cached --quiet; then
  log "no content change vs mirror HEAD; will still tag $VERSION at current HEAD"
else
  git commit --quiet -m "sync $TAG_PREFIX$VERSION from monorepo $(git -C "$REPO_ROOT" rev-parse --short HEAD)"
fi
git tag -a "$VERSION" -m "ironmcp ${TAG_PREFIX}kit $VERSION"
log "pushing $DEFAULT_BRANCH + tag $VERSION ..."
git push --quiet origin "HEAD:$DEFAULT_BRANCH"
git push --quiet origin "refs/tags/$VERSION"
log "pushed mirror $MIRROR_REPO @ $VERSION"

# Optional Packagist update ping (the GitHub hook usually handles this on its own).
if [ -n "${PACKAGIST_USERNAME:-}" ] && [ -n "${PACKAGIST_TOKEN:-}" ] && [ -n "${PACKAGIST_PACKAGE:-}" ]; then
  log "pinging Packagist update for $PACKAGIST_PACKAGE ..."
  curl -sS -XPOST -H'content-type:application/json' \
    "https://packagist.org/api/update-package?username=$PACKAGIST_USERNAME&apiToken=$PACKAGIST_TOKEN" \
    -d "{\"repository\":{\"url\":\"https://packagist.org/packages/$PACKAGIST_PACKAGE\"}}" \
    >&2 || log "packagist ping failed (non-fatal)"
fi
