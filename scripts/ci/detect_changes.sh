#!/usr/bin/env bash
# Detects which DEV Terraform stacks changed since origin/develop.
#
# Single-source (F-ARCH-4): stack/module membership is resolved by
# scripts/ci/changed_stacks.py against scripts/ci/stack_map.json — no stack path
# is hardcoded here. A shared-module edit triggers only the consuming stacks.
#
# Fail-loud (CI-H3/M3, T-R6-A8(b)): if the merge-base diff cannot be computed we
# EXIT NON-ZERO with an explicit error instead of silently falling back to
# `git diff HEAD~1` (which mis-detects on squash/rebase and shallow clones).
#
# Required env vars (set in the workflow step env:):
#   FORCE          — 'true' to skip diff and force all stacks
#
# Writes to GITHUB_OUTPUT:
#   peripherals_changed — 'true' | 'false'
#   lambda_changed      — 'true' | 'false'
set -euo pipefail

CI_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PYTHON:-python3}"

if [ "${FORCE:-false}" = "true" ]; then
  echo "peripherals_changed=true" >> "$GITHUB_OUTPUT"
  echo "lambda_changed=true"      >> "$GITHUB_OUTPUT"
  echo "Forced — all DEV stacks will be applied."
  exit 0
fi

# Resolve the diff base loudly: origin/develop must be fetchable and share a
# merge-base with HEAD. No silent HEAD~1 fallback.
if ! git rev-parse --verify --quiet origin/develop >/dev/null; then
  echo "::error::detect_changes: 'origin/develop' is not available — cannot compute a reliable diff base. Ensure the workflow checks out with fetch-depth: 0 and the develop ref is fetched." >&2
  exit 1
fi

if ! MERGE_BASE="$(git merge-base origin/develop HEAD 2>/dev/null)"; then
  echo "::error::detect_changes: no merge-base between origin/develop and HEAD (shallow clone or unrelated history). Refusing to degrade to 'git diff HEAD~1'." >&2
  exit 1
fi

DIFF="$(git diff --name-only "${MERGE_BASE}...HEAD")"
echo "Changed files:"
echo "$DIFF"

# Resolve dev stack changes through the single-source map.
CHANGED_FILES="$DIFF" "$PY" "$CI_DIR/changed_stacks.py" dev --emit-github \
  | sed 's/^dev_peripherals_changed=/peripherals_changed=/; s/^dev_lambda_changed=/lambda_changed=/' \
  >> "$GITHUB_OUTPUT"
