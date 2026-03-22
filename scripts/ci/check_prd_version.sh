#!/usr/bin/env bash
# Reads VERSION, validates it hasn't been tagged as v{VERSION}-infra yet,
# and writes it to GITHUB_OUTPUT.
#
# Required env vars (must be set in workflow step env:):
#   FORCE_APPLY — 'true' to skip the tag-existence check
#
# Writes to GITHUB_OUTPUT:
#   version — current semantic version string
# Writes to GITHUB_STEP_SUMMARY.
set -euo pipefail

VERSION=$(cat VERSION | tr -d '[:space:]')
echo "version=${VERSION}" >> "$GITHUB_OUTPUT"

if [ "${FORCE_APPLY:-false}" = "true" ]; then
  echo "force_apply — skipping tag check."
elif git tag --list | grep -qx "v${VERSION}-infra"; then
  echo "::error::v${VERSION}-infra already tagged. A new PR merge to develop is required to bump VERSION."
  exit 1
fi

echo "Version v${VERSION} — OK."
echo "## Version Check" >> "$GITHUB_STEP_SUMMARY"
echo "Deploying PRD infra **v${VERSION}**" >> "$GITHUB_STEP_SUMMARY"
