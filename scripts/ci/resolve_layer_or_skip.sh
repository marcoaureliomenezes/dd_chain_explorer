#!/usr/bin/env bash
# resolve_layer_or_skip.sh — wraps resolve_layer.sh for NON-GATING advisory plan
# lanes only: plan_on_pr.yml's plan-prd-lambda job and drift_detection.yml's
# drift-prd-lambda job. Both speculatively/periodically plan prd/06_lambda even
# though the lambda-layer artifact store (s3://dm-chain-explorer-artifacts) is
# deliberately not yet provisioned during the v0.5.0 live cutover — PRD resource
# creation is operator-scoped and deferred (docs/runbooks/v0.5.0-live-cutover.md
# §5). A missing store must SKIP the advisory plan (warn + exit 0), never fail
# the job.
#
# deploy_cloud_infra.yml's prd-plan job (the pre-gate plan that feeds the
# environment-gated prd-apply) does NOT use this wrapper — it calls
# resolve_layer.sh directly and keeps failing hard on a missing artifact store:
# a real PRD deploy can never proceed without a real layer.
#
# Usage:
#   scripts/ci/resolve_layer_or_skip.sh <bucket> <prefix>
#
# Output (stdout):
#   * artifact resolved         -> resolve_layer.sh's normal
#                                  "LAYER_S3_KEY=... LAYER_SHA256=... LAYER_SHA256_B64=..."
#                                  line, followed by "skip=false".
#   * store not yet provisioned -> a "::warning::" annotation, followed by
#                                  "skip=true". Exit code is still 0 — this
#                                  case is a deliberate skip, not a failure.
#   * any other resolve_layer.sh failure (auth, corrupt metadata, malformed
#     key, ...) -> propagated verbatim to stderr; this wrapper exits non-zero
#     and never prints "skip=true" — a real failure is never masked as a skip.

set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <bucket> <prefix>" >&2
  exit 2
fi

BUCKET="$1"
PREFIX="$2"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

STDERR_FILE="$(mktemp)"
trap 'rm -f "${STDERR_FILE}"' EXIT

set +e
OUT="$(bash "${SCRIPT_DIR}/resolve_layer.sh" "${BUCKET}" "${PREFIX}" 2>"${STDERR_FILE}")"
STATUS=$?
set -e

if [ "${STATUS}" -eq 0 ]; then
  echo "${OUT}"
  echo "skip=false"
  exit 0
fi

ERR_TEXT="$(cat "${STDERR_FILE}")"
echo "${ERR_TEXT}" >&2

if echo "${ERR_TEXT}" | grep -q "No lambda-layer artifact found"; then
  echo "::warning::prd/06_lambda plan skipped — lambda layer artifact store not yet provisioned (see docs/runbooks/v0.5.0-live-cutover.md §5)."
  echo "skip=true"
  exit 0
fi

# Any other resolve_layer.sh failure (auth, corrupt metadata, malformed key, ...)
# is a real failure — never masked as a skip.
exit "${STATUS}"
