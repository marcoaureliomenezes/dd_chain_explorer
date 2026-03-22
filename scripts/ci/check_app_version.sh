#!/usr/bin/env bash
# Reads VERSION and validates that the corresponding git tag for the current
# app type has not already been deployed. Exits 1 if the tag already exists.
#
# Required env vars (must be set in workflow step env:):
#   TAG_SUFFIX — suffix appended to the verison for the expected tag:
#                ""         → checks 'v{VERSION}'     (streaming-apps)
#                "-dabs"    → checks 'v{VERSION}-dabs'
#                "-lambda"  → checks 'v{VERSION}-lambda'
#
# Writes to GITHUB_OUTPUT:
#   version — current semantic version string
set -euo pipefail

VERSION=$(cat VERSION | tr -d '[:space:]')
echo "version=${VERSION}" >> "${GITHUB_OUTPUT}"

TAG_SUFFIX="${TAG_SUFFIX:-}"
EXPECTED_TAG="v${VERSION}${TAG_SUFFIX}"

if git tag --list | grep -qx "${EXPECTED_TAG}"; then
  echo "::error::${EXPECTED_TAG} is already tagged. Bump VERSION before deploying."
  exit 1
fi

echo "Version ${EXPECTED_TAG} is new — proceeding."
