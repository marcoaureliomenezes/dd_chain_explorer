#!/usr/bin/env bash
set -euo pipefail

VERSION_FILE="${VERSION_FILE:-VERSION}"
SUFFIXES="${SUFFIXES:- -dabs -lambda}"

if [ ! -f "$VERSION_FILE" ]; then
  echo "::error::VERSION file not found: $VERSION_FILE"
  exit 1
fi

if [ -z "${GITHUB_OUTPUT:-}" ]; then
  echo "::error::GITHUB_OUTPUT is required"
  exit 1
fi

VERSION=$(tr -d '[:space:]' < "$VERSION_FILE")
if [ -z "$VERSION" ]; then
  echo "::error::VERSION is empty"
  exit 1
fi

echo "version=${VERSION}" >> "$GITHUB_OUTPUT"

for SUFFIX in $SUFFIXES; do
  EXPECTED_TAG="v${VERSION}${SUFFIX}"
  if git tag --list | grep -qx "$EXPECTED_TAG"; then
    echo "::error::${EXPECTED_TAG} is already tagged. Bump VERSION before deploying."
    exit 1
  fi
  echo "Version ${EXPECTED_TAG} is new - OK."
done
