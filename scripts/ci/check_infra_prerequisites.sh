#!/usr/bin/env bash
# Verifies that the required PRD infrastructure exists before deploying an application.
# Branches on APP_TYPE to run the appropriate set of checks.
#
# Required env vars (must be set in workflow step env:):
#   APP_TYPE — 'databricks-dabs' | 'lambda-functions'
#
# Workflow-level env vars used directly (auto-available on runner):
#   AWS_REGION      — AWS region
#   TF_STATE_BUCKET — Terraform state S3 bucket  (dabs + lambda)
#   PRD_LAMBDA_ROLE — Lambda IAM role name        (lambda only)
#
# Required env vars for dabs only (must be set in workflow step env:):
#   DATABRICKS_PROD_HOST — from secrets
set -euo pipefail

case "${APP_TYPE}" in

  # ── databricks-dabs: workspace reachability ────────────────────────────────
  databricks-dabs)
    echo "==> Checking databricks-dabs PRD prerequisites..."

    WS_URL=$(aws s3 cp "s3://${TF_STATE_BUCKET}/prd/databricks-account/terraform.tfstate" - 2>/dev/null \
      | jq -r '.outputs.databricks_workspace_url.value // empty') || WS_URL=""
    if [ -z "${WS_URL}" ]; then
      WS_URL="${DATABRICKS_PROD_HOST:-}"
    fi
    if [ -z "${WS_URL}" ]; then
      echo "::error::No Databricks workspace URL available. Run 'Deploy Infra Cloud' (prd, 05_databricks) first."
      exit 1
    fi

    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${WS_URL}" --max-time 15) || HTTP_STATUS="000"
    if [ "${HTTP_STATUS}" = "000" ]; then
      echo "::error::Databricks workspace at ${WS_URL} is unreachable."
      exit 1
    fi
    echo "Databricks workspace reachable (HTTP ${HTTP_STATUS}): ${WS_URL}"
    ;;

  # ── lambda-functions: IAM role + DynamoDB TF state ────────────────────────
  lambda-functions)
    echo "==> Checking lambda-functions PRD prerequisites..."

    ROLE_ARN=$(aws iam get-role --role-name "${PRD_LAMBDA_ROLE}" \
      --query 'Role.Arn' --output text 2>/dev/null) || ROLE_ARN=""
    if [ -z "${ROLE_ARN}" ]; then
      echo "::error::IAM role '${PRD_LAMBDA_ROLE}' not found. Run 'Deploy Infra Cloud' (prd) first."
      exit 1
    fi
    echo "IAM role found: ${ROLE_ARN}"

    TABLE=$(aws s3 cp "s3://${TF_STATE_BUCKET}/prd/peripherals/terraform.tfstate" - 2>/dev/null \
      | jq -r '.outputs.dynamodb_table_name.value // empty') || TABLE=""
    if [ -z "${TABLE}" ]; then
      echo "::error::DynamoDB table output not found in TF state. Run 'Deploy Infra Cloud' (prd, 04_peripherals) first."
      exit 1
    fi
    echo "DynamoDB table confirmed: ${TABLE}"
    ;;

  *)
    echo "::error::Unknown APP_TYPE '${APP_TYPE}'. Expected: databricks-dabs | lambda-functions"
    exit 1
    ;;
esac
