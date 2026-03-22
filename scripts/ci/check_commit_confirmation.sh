#!/usr/bin/env bash
# Validates the destroy confirmation string. Exits 1 unless CONFIRM == 'DESTROY'.
#
# Required env vars (must be set in workflow step env:):
#   CONFIRM — must be exactly the string 'DESTROY'
set -euo pipefail

if [ "${CONFIRM:-}" != "DESTROY" ]; then
  echo "::error::Confirmation must be exactly 'DESTROY'. Got: '${CONFIRM:-<empty>}'"
  exit 1
fi

echo "Destruction confirmed."
