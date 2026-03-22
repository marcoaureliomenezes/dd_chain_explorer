#!/usr/bin/env bash
# Detects which DEV Terraform modules changed since origin/develop.
#
# Required env vars (must be set in workflow step env:):
#   FORCE          — 'true' to skip diff and force all modules
#
# Workflow-level env vars used directly (auto-available on runner):
#   DEV_PERIPHERALS — e.g. services/dev/01_peripherals
#   DEV_LAMBDA      — e.g. services/dev/02_lambda
#
# Writes to GITHUB_OUTPUT:
#   peripherals_changed — 'true' | 'false'
#   lambda_changed      — 'true' | 'false'
set -euo pipefail

if [ "${FORCE:-false}" = "true" ]; then
  echo "peripherals_changed=true" >> "$GITHUB_OUTPUT"
  echo "lambda_changed=true"      >> "$GITHUB_OUTPUT"
  echo "Forced — all DEV modules will be applied."
else
  DIFF=$(git diff --name-only origin/develop...HEAD 2>/dev/null || git diff --name-only HEAD~1 HEAD)
  echo "Changed files: $DIFF"

  if echo "$DIFF" | grep -q "${DEV_PERIPHERALS}/"; then
    echo "peripherals_changed=true" >> "$GITHUB_OUTPUT"
  else
    echo "peripherals_changed=false" >> "$GITHUB_OUTPUT"
  fi

  if echo "$DIFF" | grep -q "${DEV_LAMBDA}/"; then
    echo "lambda_changed=true" >> "$GITHUB_OUTPUT"
  else
    echo "lambda_changed=false" >> "$GITHUB_OUTPUT"
  fi
fi
