#!/usr/bin/env bash
# deploy_env.sh — Sequential deploy of all Terraform modules for a given environment.
#
# Applies modules in dependency order (fail-fast: stops on first error).
# Writes per-module status lines to $GITHUB_STEP_SUMMARY.
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
TF_VERSION="${TF_VERSION:-1.7.0}"

# ── Helpers ───────────────────────────────────────────────────────────────────

summary() { echo "$*" >> "${GITHUB_STEP_SUMMARY:-/dev/null}"; }

deploy_module() {
  local module_dir="$1"   # absolute path to module directory
  local module_name="$2"  # display name for summary

  echo ""
  echo "════════════════════════════════════════════════════════"
  echo "  DEPLOYING: ${module_name}"
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

  terraform init -input=false
  terraform validate

  export MODULE_NAME="${module_name}"
  export TAIL_LINES="${TAIL_LINES:-20}"
  export GITHUB_STEP_SUMMARY="${GITHUB_STEP_SUMMARY:-/dev/null}"

  # Per-stack apply signal: tf_plan.sh writes a `tfplan.haschanges` file into THIS
  # module's working directory. Each stack therefore carries its own signal — we never
  # grep a shared append-only $GITHUB_OUTPUT with `tail -1` (the CI-C2 cross-stack
  # contamination bug). GITHUB_OUTPUT is left to its real runner value when present
  # (and tf_plan.sh degrades cleanly without it); the apply decision does NOT depend on
  # it here.
  local plan_signal_file="${module_dir}/tfplan.haschanges"
  rm -f "${plan_signal_file}"
  export PLAN_SIGNAL_FILE="${plan_signal_file}"

  # Plan
  set +e
  bash "${REPO_ROOT}/scripts/ci/tf_plan.sh"
  PLAN_RC=$?
  set -e

  if [[ "$PLAN_RC" -ne 0 ]]; then
    summary "| ❌ | ${module_name} | plan failed |"
    echo "::error::Plan failed for ${module_name}"
    exit 1
  fi

  # Apply decision derives from the per-stack signal file written by tf_plan.sh.
  # A missing signal is NOT a silent skip (the removed `/dev/null` fallback) — it
  # means the plan step did not record a decision and the run must fail loudly.
  if [[ ! -f "${plan_signal_file}" ]]; then
    summary "| ❌ | ${module_name} | missing plan signal |"
    echo "::error::Missing plan signal for ${module_name}: ${plan_signal_file} not written by tf_plan.sh"
    exit 1
  fi

  local plan_has_changes
  plan_has_changes="$(cat "${plan_signal_file}")"
  if [[ "$plan_has_changes" == "true" ]]; then
    terraform apply -input=false -auto-approve tfplan
    summary "| ✅ | ${module_name} | applied |"
  elif [[ "$plan_has_changes" == "false" ]]; then
    summary "| ✅ | ${module_name} | no changes |"
  else
    summary "| ❌ | ${module_name} | invalid plan signal |"
    echo "::error::Invalid plan signal for ${module_name}: '${plan_has_changes}' (expected true|false)"
    exit 1
  fi

  cd "${REPO_ROOT}"
}

# ── HML module order ──────────────────────────────────────────────────────────

deploy_hml() {
  local root="${REPO_ROOT}/services/hml"

  summary ""
  summary "## HML Deploy"
  summary "| Status | Module | Result |"
  summary "|--------|--------|--------|"

  deploy_module "${root}/02_vpc"              "HML/VPC"
  deploy_module "${root}/04_peripherals"      "HML/Peripherals"
  deploy_module "${root}/03_iam"              "HML/IAM"
  deploy_module "${root}/07_ecs"              "HML/ECS"

  if [[ "$SKIP_DATABRICKS" != "true" ]]; then
    deploy_module "${root}/05_databricks"     "HML/Databricks"
    # 05b uses workspace-level PAT token from TF remote state.
    # Unset OAuth env vars to avoid "two auth methods" conflict with the token-based provider.
    (unset DATABRICKS_ACCOUNT_ID DATABRICKS_CLIENT_ID DATABRICKS_CLIENT_SECRET; \
      deploy_module "${root}/05b_databricks_workspace" "HML/DatabricksWorkspace")
  else
    summary "| ⏭️ | HML/Databricks | skipped (SKIP_DATABRICKS=true) |"
    summary "| ⏭️ | HML/DatabricksWorkspace | skipped |"
  fi

  summary ""
  summary "> HML deploy complete."
}

# ── PRD module order ──────────────────────────────────────────────────────────

deploy_prd() {
  local root="${REPO_ROOT}/services/prd"

  summary ""
  summary "## PRD Deploy"
  summary "| Status | Module | Result |"
  summary "|--------|--------|--------|"

  deploy_module "${root}/02_vpc"              "PRD/VPC"
  deploy_module "${root}/04_peripherals"      "PRD/Peripherals"
  deploy_module "${root}/03_iam"              "PRD/IAM"

  # Lambda: needs .lambda_zip dir
  mkdir -p "${root}/06_lambda/.lambda_zip"
  deploy_module "${root}/06_lambda"           "PRD/Lambda"

  deploy_module "${root}/07_ecs"              "PRD/ECS"

  if [[ "$SKIP_DATABRICKS" != "true" ]]; then
    # 05a: idempotent import first
    cd "${root}/05a_databricks_account"
    terraform init -input=false
    bash "${REPO_ROOT}/scripts/ci/databricks_account_import.sh"
    cd "${REPO_ROOT}"

    deploy_module "${root}/05a_databricks_account" "PRD/DatabricksAccount"

    # Read workspace URL output for 05b
    cd "${root}/05a_databricks_account"
    WORKSPACE_URL=$(terraform output -raw databricks_workspace_url 2>/dev/null || true)
    if [[ -z "$WORKSPACE_URL" ]]; then
      echo "::warning::Could not read workspace_url from 05a output — attempting API fallback"
      TOKEN=$(curl -sf -X POST \
        "https://accounts.cloud.databricks.com/oidc/accounts/${DATABRICKS_ACCOUNT_ID}/v1/token" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        --data-urlencode "grant_type=client_credentials" \
        --data-urlencode "client_id=${DATABRICKS_CLIENT_ID}" \
        --data-urlencode "client_secret=${DATABRICKS_CLIENT_SECRET}" \
        --data-urlencode "scope=all-apis" \
        | jq -r '.access_token' 2>/dev/null || true)
      if [[ -n "$TOKEN" && "$TOKEN" != "null" ]]; then
        WORKSPACE_URL=$(curl -sf \
          -H "Authorization: Bearer $TOKEN" \
          "https://accounts.cloud.databricks.com/api/2.0/accounts/${DATABRICKS_ACCOUNT_ID}/workspaces" \
          2>/dev/null \
          | jq -r '[.[] | select(.workspace_name=="dm-chain-explorer-prd")][0].workspace_url // empty' \
          2>/dev/null || true)
      fi
    fi
    cd "${REPO_ROOT}"

    if [[ -z "$WORKSPACE_URL" ]]; then
      summary "| ❌ | PRD/DatabricksWorkspace | workspace URL could not be determined |"
      echo "::error::Cannot deploy PRD/05b_databricks_workspace: workspace URL is empty"
      exit 1
    fi

    echo "workspace_url=${WORKSPACE_URL}" >> "${GITHUB_OUTPUT:-/dev/null}"
    export TF_VAR_workspace_host="${WORKSPACE_URL}"
    export TF_VAR_create_cluster="${TF_VAR_create_cluster:-true}"
    if [[ "$FAST_MODE" == "true" ]]; then
      export TF_VAR_create_cluster="false"
    fi

    deploy_module "${root}/05b_databricks_workspace" "PRD/DatabricksWorkspace"
  else
    summary "| ⏭️ | PRD/DatabricksAccount | skipped (SKIP_DATABRICKS=true) |"
    summary "| ⏭️ | PRD/DatabricksWorkspace | skipped |"
  fi

  summary ""
  summary "> PRD deploy complete."
}

# ── Entry point ───────────────────────────────────────────────────────────────

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
