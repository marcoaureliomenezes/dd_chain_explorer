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

  # State lock check (best-effort — does not fail pipeline)
  bash "${REPO_ROOT}/scripts/ci/tf_state_lock_check.sh" || true

  terraform init -input=false
  terraform validate

  export MODULE_NAME="${module_name}"
  export TAIL_LINES="${TAIL_LINES:-20}"
  export GITHUB_OUTPUT="${GITHUB_OUTPUT:-/dev/null}"
  export GITHUB_STEP_SUMMARY="${GITHUB_STEP_SUMMARY:-/dev/null}"

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

  # Apply only if plan has changes
  PLAN_HAS_CHANGES=$(grep "plan_has_changes=" "${GITHUB_OUTPUT}" 2>/dev/null | tail -1 | cut -d= -f2 || echo "false")
  if [[ "$PLAN_HAS_CHANGES" == "true" ]]; then
    terraform apply -input=false -auto-approve tfplan
    summary "| ✅ | ${module_name} | applied |"
  else
    summary "| ✅ | ${module_name} | no changes |"
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
    deploy_module "${root}/05b_databricks_workspace" "HML/DatabricksWorkspace"
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
