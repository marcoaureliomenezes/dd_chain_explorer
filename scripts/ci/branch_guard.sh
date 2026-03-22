#!/usr/bin/env bash
# Validates the workflow was triggered from refs/heads/develop.
# Uses the default GitHub Actions env var GITHUB_REF — no explicit env: mapping required.
set -euo pipefail

if [ "${GITHUB_REF}" != "refs/heads/develop" ]; then
  echo "::error::This workflow must be triggered from the 'develop' branch. Got: ${GITHUB_REF}"
  exit 1
fi

echo "Branch check passed: ${GITHUB_REF}"
