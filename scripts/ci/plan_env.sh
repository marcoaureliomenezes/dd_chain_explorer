#!/usr/bin/env bash
# plan_env.sh — pre-gate PLAN phase for the informed deploy gate (ADR-R6-4/R6-5).
#
# Reads the single-source stack map (scripts/ci/stack_map.json) and, for the given
# environment, plans every stack that is plannable against CURRENT state. For each:
#   - terraform init + validate + plan (via tf_plan.sh) producing tfplan + plan.txt;
#   - the tfplan binary + full plan.txt are left under $PLAN_ARTIFACT_DIR/<stack-id>/
#     so the workflow can upload them as artifacts and the apply phase can re-use the
#     SAVED approved plan binary;
#   - a consolidated add/change/destroy summary row per stack is written to the run
#     summary BEFORE the environment gate.
# Stacks marked bootstrap_plannable:false in the map whose upstream output is not yet
# available are listed as "deferred to post-upstream stage" — never silently skipped.
#
# After planning, runs the destroy-acknowledgment gate (plan_gate_check.sh destroy-ack)
# across all produced plan.txt files: any pending destroy without DESTROY_ACK fails the
# plan phase loudly so the gate reviewer is never asked to approve an unacknowledged
# destroy.
#
# Usage:
#   bash scripts/ci/plan_env.sh <hml|prd>
#
# Required env vars:
#   AWS credentials configured on the runner (plan reads remote state).
#   DESTROY_ACK            — 'true' to acknowledge destroys (default: false).
# Optional:
#   PLAN_ARTIFACT_DIR      — where to stage per-stack tfplan/plan.txt (default:
#                            $REPO_ROOT/.plan-artifacts).
#   STACK_MAP              — path to the stack map JSON (default: scripts/ci/stack_map.json).
#   TF_VERSION             — terraform version label (informational).
#   Any TF_VAR_* required by the stacks must be exported by the caller.
set -euo pipefail

ENV="${1:-}"
if [[ -z "$ENV" ]]; then
  echo "::error::Usage: plan_env.sh <hml|prd>"
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STACK_MAP="${STACK_MAP:-${REPO_ROOT}/scripts/ci/stack_map.json}"
PLAN_ARTIFACT_DIR="${PLAN_ARTIFACT_DIR:-${REPO_ROOT}/.plan-artifacts}"
DESTROY_ACK="${DESTROY_ACK:-false}"

GITHUB_STEP_SUMMARY="${GITHUB_STEP_SUMMARY:-/dev/null}"
export GITHUB_STEP_SUMMARY

if ! command -v jq >/dev/null 2>&1; then
  echo "::error::jq is required by plan_env.sh"
  exit 1
fi
if [[ ! -f "$STACK_MAP" ]]; then
  echo "::error::stack map not found: ${STACK_MAP}"
  exit 1
fi

summary() { echo "$*" >> "${GITHUB_STEP_SUMMARY}"; }

mkdir -p "${PLAN_ARTIFACT_DIR}"

summary ""
summary "## Plan phase — \`${ENV}\` (pre-gate)"
summary ""
summary "| Stack | add | change | destroy | status |"
summary "|-------|-----|--------|---------|--------|"

mapfile -t STACK_IDS < <(jq -r --arg e "$ENV" '.environments[$e].stacks[].id' "$STACK_MAP")
if [[ "${#STACK_IDS[@]}" -eq 0 ]]; then
  echo "::error::No stacks declared for environment '${ENV}' in ${STACK_MAP}"
  exit 1
fi

PLAN_TXT_FILES=()

for sid in "${STACK_IDS[@]}"; do
  label="$(jq -r --arg e "$ENV" --arg s "$sid" \
    '.environments[$e].stacks[] | select(.id==$s) | .label' "$STACK_MAP")"
  rel_path="$(jq -r --arg e "$ENV" --arg s "$sid" \
    '.environments[$e].stacks[] | select(.id==$s) | .path' "$STACK_MAP")"
  bootstrap_plannable="$(jq -r --arg e "$ENV" --arg s "$sid" \
    '.environments[$e].stacks[] | select(.id==$s) | .bootstrap_plannable' "$STACK_MAP")"

  module_dir="${REPO_ROOT}/${rel_path}"
  stage_dir="${PLAN_ARTIFACT_DIR}/${sid}"
  mkdir -p "${stage_dir}"

  if [[ ! -d "${module_dir}" ]]; then
    echo "::error::Stack '${sid}' path does not exist: ${module_dir}"
    exit 1
  fi

  echo ""
  echo "════════════════════════════════════════════════════════"
  echo "  PLAN: ${label}  (${rel_path})"
  echo "════════════════════════════════════════════════════════"

  cd "${module_dir}"
  terraform init -input=false

  # Decide plannability: a stack flagged non-bootstrap-plannable is only deferred when
  # its state does not yet exist (e.g. 05b before 05a's first apply). If terraform can
  # already plan it (state present), we plan it normally.
  set +e
  terraform validate >/dev/null 2>&1
  VALIDATE_RC=$?
  set -e
  if [[ "${VALIDATE_RC}" -ne 0 ]]; then
    echo "::error::terraform validate failed for ${label}"
    summary "| ${label} | - | - | - | ❌ validate failed |"
    exit 1
  fi

  export MODULE_NAME="${label}"
  export TAIL_LINES="${TAIL_LINES:-20}"
  export PLAN_SIGNAL_FILE="${module_dir}/tfplan.haschanges"

  set +e
  bash "${REPO_ROOT}/scripts/ci/tf_plan.sh"
  PLAN_RC=$?
  set -e

  if [[ "${PLAN_RC}" -ne 0 ]]; then
    if [[ "${bootstrap_plannable}" == "false" ]]; then
      # Non-plannable stack with absent upstream output — defer, never silently skip.
      echo "::notice::${label} cannot be planned yet (upstream output absent) — deferred to post-upstream stage."
      summary "| ${label} | - | - | - | ⏭️ deferred to post-upstream stage |"
      cd "${REPO_ROOT}"
      continue
    fi
    echo "::error::Plan failed for ${label}"
    summary "| ${label} | - | - | - | ❌ plan failed |"
    exit 1
  fi

  # Stage the saved plan binary + full plan.txt for artifact upload + apply re-use.
  cp -f tfplan "${stage_dir}/tfplan"
  cp -f plan.txt "${stage_dir}/plan.txt"
  PLAN_TXT_FILES+=("${stage_dir}/plan.txt")

  read -r add change destroy < <(
    bash "${REPO_ROOT}/scripts/ci/plan_gate_check.sh" counts "${stage_dir}/plan.txt"
  )
  summary "| ${label} | ${add} | ${change} | ${destroy} | ✅ planned |"

  cd "${REPO_ROOT}"
done

summary ""

# Destroy acknowledgment gate over every planned stack (ADR-R6-4).
if [[ "${#PLAN_TXT_FILES[@]}" -gt 0 ]]; then
  set +e
  bash "${REPO_ROOT}/scripts/ci/plan_gate_check.sh" destroy-ack "${DESTROY_ACK}" "${PLAN_TXT_FILES[@]}"
  ACK_RC=$?
  set -e
  if [[ "${ACK_RC}" -ne 0 ]]; then
    summary "> ❌ Destroy acknowledgment required: one or more plans destroy resources and the acknowledgment input was not set."
    exit "${ACK_RC}"
  fi
fi

summary "> Plan phase complete — review the per-stack summary above, then approve the environment gate to apply."
echo ""
echo "✅ plan_env.sh ${ENV} — plan phase DONE"
