#!/usr/bin/env bash
# deploy_env.sh — Sequential, map-driven apply of all Terraform stacks for an env.
#
# The post-gate APPLY phase of the informed gate (ADR-R6-4/R6-5). The stack list and
# dependency order are NOT hardcoded here — they are read from the single-source map
# scripts/ci/stack_map.json (F-ARCH-4 / F-QA-A1-3). For each stack, in declared order:
#
#   - If NONE of the stack's upstreams applied a change in this run AND a saved approved
#     plan binary exists under $PLAN_ARTIFACT_DIR/<id>/tfplan, apply that SAVED approved
#     plan directly (terraform apply tfplan) — exactly what the gate approver reviewed.
#   - Otherwise (an upstream changed in-run, OR the stack had no pre-gate plan, e.g. the
#     bootstrap_plannable:false 05b), RE-PLAN against current state and run
#     `plan_gate_check.sh plan-diff <approved.txt> <replan.txt>`:
#       * exit 0  → re-plan matches the approved summary → apply the fresh tfplan;
#       * exit 3  → DIVERGENCE → FAIL CLOSED (no further downstream applies), publishing
#                   the approved-vs-re-plan diff to the job summary + a diff artifact.
#         Re-approval = the operator re-triggers the deploy; the re-run's full re-plan
#         passes the NORMAL informed environment gate (ADR-R6-5 pinned mechanism).
#
# This guarantees ADR-R6-5 "No silent divergence, ever": apply never executes a plan the
# approver did not see without the divergence guard asserting it matches the approved one.
#
# Usage:
#   bash scripts/ci/deploy_env.sh <environment>
#
# Arguments:
#   environment — hml | prd
#
# Required env vars (hml):
#   DATABRICKS_ACCOUNT_ID, DATABRICKS_CLIENT_ID, DATABRICKS_CLIENT_SECRET
#   AWS credentials must already be configured on the runner.
#
# Required env vars (prd):
#   DATABRICKS_ACCOUNT_ID, DATABRICKS_CLIENT_ID, DATABRICKS_CLIENT_SECRET
#   TF_VAR_databricks_client_id, TF_VAR_databricks_client_secret
#   Optional: SKIP_DATABRICKS=true, FAST_MODE=true
#
# Optional env vars:
#   PLAN_ARTIFACT_DIR — where the apply job downloaded the saved pre-gate plans
#                       (default: $REPO_ROOT/.plan-artifacts).
#   STACK_MAP         — path to the stack map JSON (default scripts/ci/stack_map.json).
#   DIVERGENCE_DIR    — where to write the published divergence diff (default:
#                       $REPO_ROOT/.plan-divergence).
#   TF_BIN            — terraform binary (default: terraform). Overridable for hermetic
#                       tests via a stub on PATH.
#
# Writes to GITHUB_OUTPUT (prd only):
#   workspace_url — Databricks workspace URL (from 05a output, used by 05b)
set -euo pipefail

ENV="${1:-}"
if [[ -z "$ENV" ]]; then
  echo "::error::Usage: deploy_env.sh <hml|prd>"
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SKIP_DATABRICKS="${SKIP_DATABRICKS:-false}"
FAST_MODE="${FAST_MODE:-false}"
TF_VERSION="${TF_VERSION:-1.9.8}"
TF_BIN="${TF_BIN:-terraform}"
STACK_MAP="${STACK_MAP:-${REPO_ROOT}/scripts/ci/stack_map.json}"
PLAN_ARTIFACT_DIR="${PLAN_ARTIFACT_DIR:-${REPO_ROOT}/.plan-artifacts}"
DIVERGENCE_DIR="${DIVERGENCE_DIR:-${REPO_ROOT}/.plan-divergence}"

if ! command -v jq >/dev/null 2>&1; then
  echo "::error::jq is required by deploy_env.sh"
  exit 1
fi
if [[ ! -f "$STACK_MAP" ]]; then
  echo "::error::stack map not found: ${STACK_MAP}"
  exit 1
fi

# ── Helpers ───────────────────────────────────────────────────────────────────

summary() { echo "$*" >> "${GITHUB_STEP_SUMMARY:-/dev/null}"; }

# Stacks that applied a change in this run (by id). A downstream stack of any of these
# must be re-planned + divergence-checked, never applied from its stale saved plan.
APPLIED_STACKS=()

stack_field() {
  local sid="$1" field="$2"
  jq -r --arg e "$ENV" --arg s "$sid" --arg f "$field" \
    '.environments[$e].stacks[] | select(.id==$s) | .[$f]' "$STACK_MAP"
}

stack_upstreams() {
  local sid="$1"
  jq -r --arg e "$ENV" --arg s "$sid" \
    '.environments[$e].stacks[] | select(.id==$s) | .upstreams[]?' "$STACK_MAP"
}

# Return 0 if any upstream of <sid> is in APPLIED_STACKS (i.e. changed in-run).
upstream_applied_changes() {
  local sid="$1" up applied
  while IFS= read -r up; do
    [[ -z "$up" ]] && continue
    for applied in "${APPLIED_STACKS[@]:-}"; do
      [[ "$up" == "$applied" ]] && return 0
    done
  done < <(stack_upstreams "$sid")
  return 1
}

# Apply one stack from the map (id). Consumes the saved approved plan when the stack's
# upstreams were unchanged in-run; otherwise re-plans and divergence-gates (ADR-R6-5).
# $1 = stack id; $2 = module_dir (absolute, allows callers to pass a special-cased dir).
deploy_stack() {
  local sid="$1"
  local module_dir="$2"
  local module_name
  module_name="$(stack_field "$sid" label)"

  echo ""
  echo "════════════════════════════════════════════════════════"
  echo "  DEPLOYING: ${module_name}  (stack: ${sid})"
  echo "  DIR:  ${module_dir}"
  echo "════════════════════════════════════════════════════════"

  cd "${module_dir}"

  # State lock check — fails the run loudly on a real lock (CI-C2 / F-QA-4).
  # A stale or active state lock must NOT be swallowed: applying over a held lock
  # races another writer and can corrupt remote state.
  if ! bash "${REPO_ROOT}/scripts/ci/tf_state_lock_check.sh"; then
    summary "| ❌ | ${module_name} | state lock check failed |"
    echo "::error::State lock check failed for ${module_name}"
    exit 1
  fi

  "${TF_BIN}" init -input=false
  "${TF_BIN}" validate

  local approved_plan="${PLAN_ARTIFACT_DIR}/${sid}/tfplan"
  local approved_txt="${PLAN_ARTIFACT_DIR}/${sid}/plan.txt"

  # A stack DECLARED bootstrap_plannable:false in the map is "deferred" — the pre-gate
  # summary tells the approver it will be planned post-upstream (ADR-R6-5 "deferred,
  # never skipped"). Its no-approved-plan re-plan takes the informed deferred path, not
  # an unconditional fail-closed. Any OTHER stack missing an approved plan IS a contract
  # break and must fail closed.
  local deferred="false"
  if [[ "$(stack_field "$sid" bootstrap_plannable)" == "false" ]]; then
    deferred="true"
  fi

  if upstream_applied_changes "${sid}"; then
    echo "::notice::${module_name}: an upstream applied changes in-run — re-planning and divergence-checking against the approved plan (ADR-R6-5)."
    deploy_stack_replan_diff "${sid}" "${module_name}" "${approved_txt}" "${deferred}"
  elif [[ -f "${approved_plan}" ]]; then
    # Upstreams unchanged → apply the SAVED approved plan binary the gate reviewer saw.
    echo "::notice::${module_name}: upstreams unchanged — applying the saved approved plan."
    if grep -qE '^No changes\.' "${approved_txt}" 2>/dev/null; then
      summary "| ✅ | ${module_name} | no changes (saved plan) |"
    else
      "${TF_BIN}" apply -input=false -auto-approve "${approved_plan}"
      summary "| ✅ | ${module_name} | applied saved approved plan |"
      APPLIED_STACKS+=("${sid}")
    fi
  elif [[ "${deferred}" == "true" ]]; then
    # Declared-deferred stack (e.g. 05b) with no pre-gate plan — the approver was already
    # told this stack is "deferred to post-upstream stage". Re-plan now (upstream outputs
    # are available) and apply the informed post-gate re-plan; the divergence gate runs in
    # --deferred mode so a missing-approved plan is the deferred path, not exit 3. The
    # destroy-ack gate still protects it.
    echo "::notice::${module_name}: declared-deferred stack, no pre-gate plan — informed post-gate re-plan (ADR-R6-5 deferred path)."
    deploy_stack_replan_diff "${sid}" "${module_name}" "${approved_txt}" "${deferred}"
  else
    # A non-deferred stack with NO approved plan is a broken contract: plan_gate_check.sh
    # plan-diff fails closed (exit 3) on the missing approved plan.
    echo "::notice::${module_name}: no saved approved plan — re-planning and divergence-checking (ADR-R6-5)."
    deploy_stack_replan_diff "${sid}" "${module_name}" "${approved_txt}" "${deferred}"
  fi

  cd "${REPO_ROOT}"
}

# Re-plan the current stack (cwd is the module dir) and gate the fresh plan against the
# approved summary via plan_gate_check.sh plan-diff. Fail closed (exit ≠ 0) on divergence.
deploy_stack_replan_diff() {
  local sid="$1" module_name="$2" approved_txt="$3" deferred="${4:-false}"

  export MODULE_NAME="${module_name}"
  export TAIL_LINES="${TAIL_LINES:-20}"
  export GITHUB_STEP_SUMMARY="${GITHUB_STEP_SUMMARY:-/dev/null}"

  local plan_signal_file="${PWD}/tfplan.haschanges"
  rm -f "${plan_signal_file}"
  export PLAN_SIGNAL_FILE="${plan_signal_file}"

  set +e
  bash "${REPO_ROOT}/scripts/ci/tf_plan.sh"
  local plan_rc=$?
  set -e
  if [[ "$plan_rc" -ne 0 ]]; then
    summary "| ❌ | ${module_name} | re-plan failed |"
    echo "::error::Re-plan failed for ${module_name}"
    exit 1
  fi
  if [[ ! -f "${plan_signal_file}" ]]; then
    summary "| ❌ | ${module_name} | missing plan signal |"
    echo "::error::Missing plan signal for ${module_name}: ${plan_signal_file} not written by tf_plan.sh"
    exit 1
  fi

  # Divergence gate: compare the fresh re-plan (plan.txt, written by tf_plan.sh in cwd)
  # against the approved pre-gate summary. exit 3 = divergence → fail closed.
  # For a declared-deferred stack with no approved plan, pass --deferred so the missing
  # approved plan is the informed post-gate path (ADR-R6-5), not unconditional exit 3.
  local replan_txt="${PWD}/plan.txt"
  local diff_args=(plan-diff)
  if [[ "$deferred" == "true" && ! -f "$approved_txt" ]]; then
    diff_args+=(--deferred)
    # The approver never saw a pre-gate plan for this deferred stack, so run the
    # destroy-ack gate over the fresh re-plan before applying it — destroys still need an
    # explicit acknowledgment even on the deferred path.
    set +e
    bash "${REPO_ROOT}/scripts/ci/plan_gate_check.sh" destroy-ack "${DESTROY_ACK:-false}" "${replan_txt}"
    local ack_rc=$?
    set -e
    if [[ "$ack_rc" -ne 0 ]]; then
      summary "| ❌ | ${module_name} | deferred re-plan destroys without acknowledgment |"
      echo "::error::${module_name}: deferred re-plan contains destroys but DESTROY_ACK is not set."
      exit "$ack_rc"
    fi
  fi
  set +e
  local diff_out
  diff_out="$(bash "${REPO_ROOT}/scripts/ci/plan_gate_check.sh" "${diff_args[@]}" "${approved_txt}" "${replan_txt}" 2>&1)"
  local diff_rc=$?
  set -e
  echo "${diff_out}"

  if [[ "$diff_rc" -eq 3 ]]; then
    mkdir -p "${DIVERGENCE_DIR}"
    local div_file="${DIVERGENCE_DIR}/${sid}.diff.txt"
    printf '%s\n' "${diff_out}" > "${div_file}"
    summary "| ❌ | ${module_name} | re-plan DIVERGES from approved plan — failed closed |"
    summary ""
    summary "<details><summary>Divergence diff (${module_name})</summary>"
    summary ""
    summary '```'
    summary "${diff_out}"
    summary '```'
    summary "</details>"
    echo "::error::${module_name}: re-plan diverges from the approved plan — failing closed (no further downstream applies). Diff: ${div_file}"
    exit 3
  elif [[ "$diff_rc" -ne 0 ]]; then
    summary "| ❌ | ${module_name} | plan-diff gate error (rc=${diff_rc}) |"
    echo "::error::plan-diff gate errored for ${module_name} (rc=${diff_rc})"
    exit "${diff_rc}"
  fi

  # Re-plan matches the approved summary → safe to apply the fresh tfplan.
  local plan_has_changes
  plan_has_changes="$(cat "${plan_signal_file}")"
  if [[ "$plan_has_changes" == "true" ]]; then
    "${TF_BIN}" apply -input=false -auto-approve tfplan
    summary "| ✅ | ${module_name} | re-plan matched approved — applied |"
    APPLIED_STACKS+=("${sid}")
  elif [[ "$plan_has_changes" == "false" ]]; then
    summary "| ✅ | ${module_name} | no changes (re-plan) |"
  else
    summary "| ❌ | ${module_name} | invalid plan signal |"
    echo "::error::Invalid plan signal for ${module_name}: '${plan_has_changes}' (expected true|false)"
    exit 1
  fi
}

# ── HML deploy ────────────────────────────────────────────────────────────────

deploy_hml() {
  summary ""
  summary "## HML Deploy"
  summary "| Status | Module | Result |"
  summary "|--------|--------|--------|"

  # Stack order + membership are the map's declared order (T-A.8, F-ARCH-4) minus
  # operator_only stacks — scripts/ci/stack_list.sh is the ONE place that resolves it.
  local sid path
  while IFS= read -r sid; do
    path="$(stack_field "$sid" path)"
    deploy_stack "$sid" "${REPO_ROOT}/${path}"
  done < <(bash "${REPO_ROOT}/scripts/ci/stack_list.sh" hml)

  summary ""
  summary "> HML deploy complete."
}

# ── PRD deploy ────────────────────────────────────────────────────────────────

deploy_prd() {
  summary ""
  summary "## PRD Deploy"
  summary "| Status | Module | Result |"
  summary "|--------|--------|--------|"

  # Stack order + membership are the map's declared order (T-A.8, F-ARCH-4) minus
  # operator_only stacks (00_bootstrap, D14/O-1) — scripts/ci/stack_list.sh resolves it.
  local sid path
  while IFS= read -r sid; do
    path="$(stack_field "$sid" path)"
    if [[ "$sid" == "lambda" ]]; then
      # Lambda: needs .lambda_zip dir
      mkdir -p "${REPO_ROOT}/${path}/.lambda_zip"
    fi
    deploy_stack "$sid" "${REPO_ROOT}/${path}"
  done < <(bash "${REPO_ROOT}/scripts/ci/stack_list.sh" prd)

  summary ""
  summary "> PRD deploy complete."
}


# ── Entry point ───────────────────────────────────────────────────────────────
# Guard: when sourced (DEPLOY_ENV_SOURCE_ONLY=1) expose the helper functions for
# hermetic unit tests without running a deploy. Otherwise run the env's deploy.
if [[ "${DEPLOY_ENV_SOURCE_ONLY:-}" != "1" ]]; then
  summary ""
  summary "## Deploy \`${ENV}\` — $(date -u '+%Y-%m-%d %H:%M UTC')"
  summary ""

  case "$ENV" in
    hml) deploy_hml ;;
    prd) deploy_prd ;;
    *)
      echo "::error::Unknown environment '${ENV}'. Supported: hml, prd"
      exit 1
      ;;
  esac

  echo ""
  echo "✅ deploy_env.sh ${ENV} — DONE"
fi
