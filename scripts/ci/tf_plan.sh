#!/usr/bin/env bash
# Runs `terraform plan` with detailed exit-code handling, writes plan_has_changes
# to GITHUB_OUTPUT, and always appends a plan summary block to GITHUB_STEP_SUMMARY
# (even on failure, so the summary is visible when debugging).
#
# Replaces the repeated plan-step + `if: always()` summary-injection step pair.
#
# Required env vars (must be set in workflow step env:):
#   MODULE_NAME — display label used in the summary heading, e.g. "PRD/VPC"
#
# Optional env vars:
#   TAIL_LINES  — number of plan lines to show in summary (default: 15)
#
# Any TF_VAR_* vars needed by the specific plan must also be passed in the step env:.
#
# Writes to GITHUB_OUTPUT:
#   plan_has_changes — 'true' if plan has pending changes (exit code 2), 'false' otherwise
set -euo pipefail

MODULE_NAME="${MODULE_NAME:-Terraform}"
TAIL_LINES="${TAIL_LINES:-15}"

set +e
terraform plan -no-color -input=false -out=tfplan -detailed-exitcode > plan.txt 2>&1
PLAN_EXIT=$?
set -e

# Always inject summary so it appears even if the plan errored
echo "### Plan ${MODULE_NAME}" >> "${GITHUB_STEP_SUMMARY}"
echo '```hcl' >> "${GITHUB_STEP_SUMMARY}"
tail -"${TAIL_LINES}" plan.txt >> "${GITHUB_STEP_SUMMARY}"
echo '```' >> "${GITHUB_STEP_SUMMARY}"

if [ "${PLAN_EXIT}" -eq 1 ]; then
  echo "::error::Terraform plan failed"
  echo "--- terraform plan output (tail) ---"
  tail -80 plan.txt || true
  echo "--- end terraform plan output ---"
  exit 1
fi

if [ "${PLAN_EXIT}" -eq 2 ]; then
  echo "plan_has_changes=true" >> "${GITHUB_OUTPUT}"
else
  echo "plan_has_changes=false" >> "${GITHUB_OUTPUT}"
fi
