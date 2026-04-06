#!/usr/bin/env bash
# destroy_env.sh — Sequential destroy of all Terraform modules for a given environment.
#
# Destroys modules in REVERSE dependency order (fail-fast: stops on first error).
# Writes per-module status lines to $GITHUB_STEP_SUMMARY.
#
# IMPORTANT: set -e is used. If a module destroy fails, downstream modules are NOT
# destroyed. This prevents state inconsistency (orphaned resources that can't be
# managed because their dependencies are gone).
#
# Usage:
#   bash scripts/ci/destroy_env.sh <environment> [full_destroy]
#
# Arguments:
#   environment  — dev | hml | prd
#   full_destroy — "true" to destroy ALL HML modules (default: false = Databricks only)
#
# Required env vars (hml/prd):
#   DATABRICKS_ACCOUNT_ID, DATABRICKS_CLIENT_ID, DATABRICKS_CLIENT_SECRET
#   AWS credentials must already be configured on the runner.
#
# Required env vars (prd):
#   TF_VAR_databricks_client_id, TF_VAR_databricks_client_secret
set -euo pipefail

ENV="${1:-}"
FULL_DESTROY="${2:-false}"

if [[ -z "$ENV" ]]; then
  echo "::error::Usage: destroy_env.sh <dev|hml|prd> [full_destroy=true]"
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# ── Helpers ───────────────────────────────────────────────────────────────────

summary() { echo "$*" >> "${GITHUB_STEP_SUMMARY:-/dev/null}"; }

destroy_module() {
  local module_dir="$1"   # absolute path to module directory
  local module_name="$2"  # display name for summary
  local extra_args="${3:-}"  # optional additional terraform args (e.g. -target for S3-preserved)

  echo ""
  echo "════════════════════════════════════════════════════════"
  echo "  DESTROYING: ${module_name}"
  echo "  DIR:  ${module_dir}"
  echo "════════════════════════════════════════════════════════"

  cd "${module_dir}"

  # State lock check (best-effort)
  bash "${REPO_ROOT}/scripts/ci/tf_state_lock_check.sh" || true

  terraform init -input=false

  # shellcheck disable=SC2086
  terraform destroy -auto-approve -input=false -no-color ${extra_args}

  summary "| ✅ | ${module_name} | destroyed |"
  cd "${REPO_ROOT}"
}

# S3-preserved partial destroy (only non-S3 resources)
S3_PRESERVED_TARGETS="-target=module.dynamodb -target=module.kinesis -target=module.sqs -target=module.cloudwatch_logs"

# ── DEV destroy order ─────────────────────────────────────────────────────────

destroy_dev() {
  local root="${REPO_ROOT}/services/dev"

  summary ""
  summary "## DEV Destroy"
  summary "| Status | Module | Result |"
  summary "|--------|--------|--------|"

  # Lambda first
  mkdir -p "${root}/02_lambda/.lambda_zip"
  destroy_module "${root}/02_lambda"        "DEV/Lambda"

  # Peripherals: S3 preserved
  destroy_module "${root}/01_peripherals"   "DEV/Peripherals (S3 preserved)" "${S3_PRESERVED_TARGETS}"

  summary ""
  summary "> DEV destroy complete. S3 buckets preserved."
}

# ── HML destroy order ─────────────────────────────────────────────────────────

destroy_hml() {
  local root="${REPO_ROOT}/services/hml"

  summary ""
  summary "## HML Destroy"
  summary "| Status | Module | Result |"
  summary "|--------|--------|--------|"

  # Always destroy Databricks workspace resources first (has catalog + external locations)
  destroy_module "${root}/05b_databricks_workspace" "HML/DatabricksWorkspace"

  # Then account-level Databricks (workspace, metastore, credentials, networks)
  destroy_module "${root}/05_databricks"            "HML/Databricks"

  if [[ "$FULL_DESTROY" == "true" ]]; then
    # ECS (parallel with Databricks destroy — but sequential is safer for state consistency)
    destroy_module "${root}/07_ecs"                 "HML/ECS"

    # Peripherals: S3 preserved
    destroy_module "${root}/04_peripherals"         "HML/Peripherals (S3 preserved)" "${S3_PRESERVED_TARGETS}"

    # IAM after peripherals (roles may be referenced by peripherals resources)
    destroy_module "${root}/03_iam"                 "HML/IAM"

    # VPC last: wait for ENI release first
    echo "==> Waiting for ENI release before VPC destroy..."
    VPC_NAME_TAG="dm-chain-explorer-hml" \
    AWS_REGION="${AWS_REGION:-sa-east-1}" \
    bash "${REPO_ROOT}/scripts/ci/wait_eni_release.sh"

    destroy_module "${root}/02_vpc"                 "HML/VPC"

    summary ""
    summary "> HML full destroy complete. S3 buckets preserved."
  else
    summary ""
    summary "> HML Databricks-only destroy complete. VPC/IAM/Peripherals/ECS preserved."
  fi
}

# ── PRD destroy order ─────────────────────────────────────────────────────────

destroy_prd() {
  local root="${REPO_ROOT}/services/prd"

  summary ""
  summary "## PRD Destroy"
  summary "| Status | Module | Result |"
  summary "|--------|--------|--------|"

  # Step 0: empty ECR repos before destroying ECS
  echo "==> Emptying PRD ECR repositories..."
  bash "${REPO_ROOT}/scripts/ci/empty_s3_and_ecr.sh"
  summary "| ✅ | PRD/ECR | emptied |"

  # Lambda + ECS first (parallel-safe here but sequential avoids race conditions)
  mkdir -p "${root}/06_lambda/.lambda_zip"
  destroy_module "${root}/06_lambda"            "PRD/Lambda"
  destroy_module "${root}/07_ecs"               "PRD/ECS"

  # Databricks workspace resources (catalog, external locations, credentials)
  # Resolve workspace URL for 05b provider config
  WORKSPACE_URL=""
  cd "${root}/05a_databricks_account"
  terraform init -input=false -reconfigure 2>/dev/null || terraform init -input=false
  WORKSPACE_URL=$(terraform output -raw databricks_workspace_url 2>/dev/null || true)
  if [[ -z "$WORKSPACE_URL" ]]; then
    echo "::warning::TF output returned empty workspace URL — trying Databricks API fallback"
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

  if [[ -n "$WORKSPACE_URL" ]]; then
    export TF_VAR_workspace_host="${WORKSPACE_URL}"
  fi

  destroy_module "${root}/05b_databricks_workspace" "PRD/DatabricksWorkspace"

  # Databricks account-level: import before destroy
  cd "${root}/05a_databricks_account"
  bash "${REPO_ROOT}/scripts/ci/databricks_account_import.sh"
  cd "${REPO_ROOT}"

  destroy_module "${root}/05a_databricks_account" "PRD/DatabricksAccount"

  # Peripherals: S3 preserved
  destroy_module "${root}/04_peripherals" "PRD/Peripherals (S3 preserved)" "${S3_PRESERVED_TARGETS}"

  # IAM
  destroy_module "${root}/03_iam" "PRD/IAM"

  # VPC last: wait for ENI release first
  echo "==> Waiting for ENI release before VPC destroy..."
  VPC_NAME_TAG="dm-chain-explorer-prd" \
  AWS_REGION="${AWS_REGION:-sa-east-1}" \
  bash "${REPO_ROOT}/scripts/ci/wait_eni_release.sh"

  destroy_module "${root}/02_vpc" "PRD/VPC"

  summary ""
  summary "> PRD destroy complete. S3 buckets and DynamoDB lock table preserved."
}

# ── Entry point ───────────────────────────────────────────────────────────────

summary ""
summary "## Destroy \`${ENV}\` — $(date -u '+%Y-%m-%d %H:%M UTC')"
if [[ "$ENV" == "hml" && "$FULL_DESTROY" == "true" ]]; then
  summary "> Mode: **full destroy** (all modules)"
elif [[ "$ENV" == "hml" ]]; then
  summary "> Mode: **Databricks-only** (VPC/IAM/Peripherals/ECS preserved)"
fi
summary ""

case "$ENV" in
  dev) destroy_dev  ;;
  hml) destroy_hml  ;;
  prd) destroy_prd  ;;
  *)
    echo "::error::Unknown environment '${ENV}'. Supported: dev, hml, prd"
    exit 1
    ;;
esac

echo ""
echo "✅ destroy_env.sh ${ENV} — DONE"
