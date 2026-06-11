#!/usr/bin/env bash
# Runs `terraform plan` with detailed exit-code handling, writes plan_has_changes
# to GITHUB_OUTPUT (for GH-native gating), writes a per-stack signal file
# `tfplan.haschanges` in the module's own working directory (for the sequential
# deploy_env.sh wrapper), and always appends a plan summary block to
# GITHUB_STEP_SUMMARY (even on failure, so the summary is visible when debugging).
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
#
# Writes to the current working directory (per-stack apply signal — CI-C2):
#   tfplan.haschanges — single line 'true' | 'false'. Co-located with the `tfplan`
#                       binary it describes, so each stack carries its own signal and
#                       sequential callers never cross-contaminate decisions by reading
#                       a shared append-only $GITHUB_OUTPUT with `tail -1`.
set -euo pipefail

MODULE_NAME="${MODULE_NAME:-Terraform}"
TAIL_LINES="${TAIL_LINES:-15}"

# GH-native gating channel. On a real runner GITHUB_OUTPUT/GITHUB_STEP_SUMMARY are set;
# off-runner (sequential deploy_env.sh wrapper or local tests) they default to /dev/null.
# The per-stack apply decision does NOT depend on GITHUB_OUTPUT — it is written to the
# PLAN_SIGNAL_FILE below — so this default is purely for the GH-native channel.
GITHUB_OUTPUT="${GITHUB_OUTPUT:-/dev/null}"
GITHUB_STEP_SUMMARY="${GITHUB_STEP_SUMMARY:-/dev/null}"

# Per-stack signal file path — co-located with the plan binary in the cwd.
PLAN_SIGNAL_FILE="${PLAN_SIGNAL_FILE:-tfplan.haschanges}"

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
  # Do not leave a stale signal file from a previous successful run — a failed plan
  # has no apply decision and must not let a caller apply a stale tfplan.
  rm -f "${PLAN_SIGNAL_FILE}"
  echo "::error::Terraform plan failed"
  echo "--- terraform plan output (tail) ---"
  tail -80 plan.txt || true
  echo "--- end terraform plan output ---"
  exit 1
fi

if [ "${PLAN_EXIT}" -eq 2 ]; then
  echo "plan_has_changes=true" >> "${GITHUB_OUTPUT}"
  echo "true" > "${PLAN_SIGNAL_FILE}"
else
  echo "plan_has_changes=false" >> "${GITHUB_OUTPUT}"
  echo "false" > "${PLAN_SIGNAL_FILE}"
fi
