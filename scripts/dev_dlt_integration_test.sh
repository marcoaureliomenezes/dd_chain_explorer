#!/usr/bin/env bash
# =============================================================================
# DEV DLT Integration Test — End-to-End
#
# Orchestrates a full DLT integration test in the DEV environment:
#   1. Deploys DABs bundle to DEV target
#   2. Triggers DLT pipelines (full refresh) via workflow
#   3. Waits for pipeline completion
#   4. Validates Gold MVs have data (calls hml_dlt_integration_test.sh)
#
# This script replaces Databricks workflows for orchestration — the CI/CD
# pipeline (GitHub Actions) is responsible for orchestration, not Databricks.
#
# Prerequisites:
#   • Databricks CLI configured (profile or env vars)
#   • AWS CLI configured (for S3 cleanup if needed)
#   • Data flowing from Firehose → S3 raw/ prefix
#   • DATABRICKS_HOST and DATABRICKS_TOKEN env vars set
#
# Usage:
#   bash scripts/dev_dlt_integration_test.sh
#
# Environment variables (all have defaults for DEV):
#   DATABRICKS_HOST   — workspace URL (default: https://dbc-409f1007-5779.cloud.databricks.com)
#   DATABRICKS_TOKEN  — PAT token (required)
#   CATALOG           — Unity Catalog name (default: dev)
#   WAREHOUSE_ID      — SQL Warehouse ID (default: a2a66f2adb0faf18)
#   TARGET            — DABs target (default: dev)
#   FULL_REFRESH      — true/false (default: true)
#   SKIP_DEPLOY       — skip DABs deploy step (default: false)
#   SKIP_CLEANUP      — skip S3 DLT data cleanup (default: false)
#
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── Configuration ─────────────────────────────────────────────────────────────
DATABRICKS_HOST="${DATABRICKS_HOST:-https://dbc-409f1007-5779.cloud.databricks.com}"
DATABRICKS_TOKEN="${DATABRICKS_TOKEN:?DATABRICKS_TOKEN is required}"
CATALOG="${CATALOG:-dev}"
WAREHOUSE_ID="${WAREHOUSE_ID:-a2a66f2adb0faf18}"
TARGET="${TARGET:-dev}"
FULL_REFRESH="${FULL_REFRESH:-true}"
SKIP_DEPLOY="${SKIP_DEPLOY:-false}"
SKIP_CLEANUP="${SKIP_CLEANUP:-false}"

# S3 bucket for DLT external table data (bronze/silver/gold/checkpoints)
S3_BUCKET="dm-chain-explorer-${TARGET}-ingestion"

# Workflow names (as defined in DABs — includes target name_prefix)
WORKFLOW_FULL_REFRESH="[${TARGET} dd_chain_explorer] dm-dlt-full-refresh"
WORKFLOW_TRIGGER_ALL="[${TARGET} dd_chain_explorer] dm-trigger-dlt-all"

# DynamoDB table and Lambda function name (used for Lambda chain validation)
DYNAMODB_TABLE="dm-chain-explorer-${TARGET}"
LAMBDA_FUNC="dd-chain-explorer-${TARGET}-gold-to-dynamodb"

# Pipeline run timeout — 3 tasks: full_refresh_ethereum + full_refresh_app_logs + export_gold_to_s3
PIPELINE_TIMEOUT=1800  # 30 minutes

# ── Utilities ─────────────────────────────────────────────────────────────────
log()  { echo "[$(date -u '+%H:%M:%S')] $*"; }
ok()   { log "✅ $*"; }
fail() { log "❌ $*"; exit 1; }
warn() { log "⚠️  $*"; }

SCRIPT_START=$(date +%s)

# =============================================================================
log "══════════════════════════════════════════════════════════════════════"
log "  DEV DLT Integration Test"
log "  TARGET=${TARGET}  CATALOG=${CATALOG}  FULL_REFRESH=${FULL_REFRESH}"
log "  DATABRICKS_HOST=${DATABRICKS_HOST}"
log "  S3_BUCKET=${S3_BUCKET}"
log "══════════════════════════════════════════════════════════════════════"
log ""

# ── Step 1: Deploy DABs ──────────────────────────────────────────────────────
if [ "$SKIP_DEPLOY" = "true" ]; then
  warn "Skipping DABs deploy (SKIP_DEPLOY=true)"
else
  log "──── Step 1: Deploying DABs to target '${TARGET}' ────"
  (
    cd "$PROJECT_ROOT/apps/dabs"
    databricks bundle deploy --target "$TARGET"
  )
  ok "DABs deployed to ${TARGET}"
fi
log ""

# ── Step 2: Cleanup DLT external table data ──────────────────────────────────
# Remove stale Delta data so full_refresh starts clean
if [ "$SKIP_CLEANUP" = "true" ]; then
  warn "Skipping S3 cleanup (SKIP_CLEANUP=true)"
else
  log "──── Step 2: Cleaning S3 DLT external table data ────"
  for LAYER in bronze silver gold checkpoints; do
    log "  Deleting s3://${S3_BUCKET}/${LAYER}/ ..."
    aws s3 rm "s3://${S3_BUCKET}/${LAYER}/" --recursive --region sa-east-1 2>/dev/null || true
  done
  ok "S3 DLT data cleaned"
fi
log ""

# ── Step 3: Verify raw data exists (blockchain + app_logs) ──────────────────
log "──── Step 3: Checking raw data in S3 ────"
RAW_COUNT=$(aws s3 ls "s3://${S3_BUCKET}/raw/" --recursive --region sa-east-1 2>/dev/null | wc -l || echo "0")
if [ "$RAW_COUNT" -gt 0 ]; then
  ok "Raw data found: ${RAW_COUNT} files in s3://${S3_BUCKET}/raw/"
else
  fail "No raw data in s3://${S3_BUCKET}/raw/ — Firehose may not be delivering. Aborting."
fi

# Wait for Firehose app_logs delivery to S3 (buffer_interval=60s in DEV)
# Containers must be running and logging to CloudWatch → subscription filter → Firehose → S3
log "  Checking raw/app_logs/ (Firehose CW Logs delivery) ..."
APP_LOGS_WAIT=300  # 5 minutes max — Firehose buffer_interval=60s in DEV
APP_LOGS_DEADLINE=$(( $(date +%s) + APP_LOGS_WAIT ))
APP_LOGS_COUNT=0
while [ "$(date +%s)" -lt "$APP_LOGS_DEADLINE" ]; do
  APP_LOGS_COUNT=$(aws s3 ls "s3://${S3_BUCKET}/raw/app_logs/" --recursive --region sa-east-1 2>/dev/null | wc -l || echo "0")
  if [ "${APP_LOGS_COUNT:-0}" -gt 0 ]; then
    ok "App logs found: ${APP_LOGS_COUNT} files in s3://${S3_BUCKET}/raw/app_logs/"
    break
  fi
  log "  → raw/app_logs/ empty, waiting 30s for Firehose delivery ... (CW subscription filter: dm-${TARGET}-logs-to-firehose)"
  sleep 30
done
if [ "${APP_LOGS_COUNT:-0}" -eq 0 ]; then
  fail "No app_logs data in s3://${S3_BUCKET}/raw/app_logs/ after ${APP_LOGS_WAIT}s.\n  Check: aws firehose describe-delivery-stream --delivery-stream-name firehose-app-logs-${TARGET}\n  Check: aws logs describe-subscription-filters --log-group-name /apps/dm-chain-explorer-${TARGET}"
fi
log ""

# ── Step 4: Trigger DLT pipelines ────────────────────────────────────────────
log "──── Step 4: Triggering DLT pipelines ────"

if [ "$FULL_REFRESH" = "true" ]; then
  WORKFLOW_NAME="$WORKFLOW_FULL_REFRESH"
  log "  Using full refresh workflow: ${WORKFLOW_NAME}"
else
  WORKFLOW_NAME="$WORKFLOW_TRIGGER_ALL"
  log "  Using incremental workflow: ${WORKFLOW_NAME}"
fi

# Trigger via databricks bundle run
RUN_OUTPUT=$(cd "$PROJECT_ROOT/apps/dabs" && \
  databricks bundle run --target "$TARGET" \
    "$([ "$FULL_REFRESH" = "true" ] && echo "workflow_dlt_full_refresh" || echo "workflow_trigger_dlt_all")" \
    --no-wait 2>&1) || fail "Failed to trigger workflow: ${RUN_OUTPUT}"

# Extract run ID from output
# Format: 'Run URL: https://...#job/JOB_ID/run/RUN_ID'
RUN_ID=$(echo "$RUN_OUTPUT" | grep -oP '/run/(\d+)' | grep -oP '\d+' | tail -1)
if [ -z "$RUN_ID" ]; then
  # Fallback: try run_id=NNN query param format
  RUN_ID=$(echo "$RUN_OUTPUT" | grep -oP 'run_id=(\d+)' | grep -oP '\d+' | head -1)
fi

if [ -z "$RUN_ID" ]; then
  log "  Bundle run output:"
  echo "$RUN_OUTPUT"
  warn "Could not extract run ID — will wait for estimated pipeline duration"
  log "  Waiting ${PIPELINE_TIMEOUT}s for pipelines to complete ..."
  sleep "$PIPELINE_TIMEOUT"
else
  ok "Workflow triggered — run_id=${RUN_ID}"

  # Poll for workflow completion
  log "  Waiting for workflow run ${RUN_ID} to complete (timeout=${PIPELINE_TIMEOUT}s) ..."
  DEADLINE=$(( $(date +%s) + PIPELINE_TIMEOUT ))

  while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    RUN_STATUS=$(curl -s -X GET \
      "${DATABRICKS_HOST}/api/2.1/jobs/runs/get?run_id=${RUN_ID}" \
      -H "Authorization: Bearer ${DATABRICKS_TOKEN}" \
      | jq -r '.state.life_cycle_state // "UNKNOWN"')

    case "$RUN_STATUS" in
      TERMINATED)
        RESULT_STATE=$(curl -s -X GET \
          "${DATABRICKS_HOST}/api/2.1/jobs/runs/get?run_id=${RUN_ID}" \
          -H "Authorization: Bearer ${DATABRICKS_TOKEN}" \
          | jq -r '.state.result_state // "UNKNOWN"')
        if [ "$RESULT_STATE" = "SUCCESS" ]; then
          ok "Workflow completed — result_state=SUCCESS"
        else
          fail "Workflow failed — result_state=${RESULT_STATE}"
        fi
        break
        ;;
      INTERNAL_ERROR)
        fail "Workflow internal error — run_id=${RUN_ID}"
        ;;
      SKIPPED)
        fail "Workflow skipped — run_id=${RUN_ID}"
        ;;
      *)
        log "  → status=${RUN_STATUS}, waiting 30s ..."
        sleep 30
        ;;
    esac
  done

  if [ "$(date +%s)" -ge "$DEADLINE" ]; then
    fail "Workflow timed out after ${PIPELINE_TIMEOUT}s — run_id=${RUN_ID}"
  fi
fi
log ""

# ── Step 5: Validate Gold MVs ────────────────────────────────────────────────
log "──── Step 5: Validating Gold Materialized Views ────"
log ""

export DATABRICKS_HOST DATABRICKS_TOKEN CATALOG WAREHOUSE_ID S3_BUCKET DYNAMODB_TABLE LAMBDA_FUNC
bash "$SCRIPT_DIR/hml_dlt_integration_test.sh"
VALIDATION_EXIT=$?

log ""

# ── Step 6: Validate Lambda → DynamoDB chain ─────────────────────────────────
log "──── Step 6: Validating Lambda → DynamoDB chain ────"
log "  Waiting for Lambda S3-event processing (export_gold_to_s3 → Lambda → DynamoDB) ..."

LAMBDA_WAIT=120  # 2 minutes for S3 event delivery + Lambda invocation
LAMBDA_DEADLINE=$(( $(date +%s) + LAMBDA_WAIT ))
DYNAMO_COUNT=0
while [ "$(date +%s)" -lt "$LAMBDA_DEADLINE" ]; do
  DYNAMO_COUNT=$(aws dynamodb query \
    --table-name "${DYNAMODB_TABLE}" \
    --key-condition-expression "pk = :pk" \
    --expression-attribute-values '{":pk":{"S":"CONSUMPTION"}}' \
    --select COUNT \
    --region sa-east-1 \
    --query 'Count' --output text 2>/dev/null || echo "0")
  if [ "${DYNAMO_COUNT:-0}" -gt 0 ]; then
    ok "Lambda chain: ${DYNAMO_COUNT} CONSUMPTION item(s) in DynamoDB table '${DYNAMODB_TABLE}'"
    break
  fi
  log "  → DynamoDB CONSUMPTION count=0, waiting 20s ..."
  sleep 20
done

if [ "${DYNAMO_COUNT:-0}" -eq 0 ]; then
  log "❌ FAIL — Lambda chain: 0 CONSUMPTION items in DynamoDB after ${LAMBDA_WAIT}s"
  log "   Check Lambda logs: aws logs tail /aws/lambda/${TARGET:+dd-chain-explorer-${TARGET}-gold-to-dynamodb} --since 10m"
  log "   Check S3 exports: aws s3 ls s3://${S3_BUCKET}/exports/gold_api_keys/ --recursive"
  LAMBDA_EXIT=1
else
  LAMBDA_EXIT=0
fi

log ""

# ── Summary ───────────────────────────────────────────────────────────────────
FINAL_EXIT=$(( VALIDATION_EXIT > LAMBDA_EXIT ? VALIDATION_EXIT : LAMBDA_EXIT ))
ELAPSED=$(( $(date +%s) - SCRIPT_START ))
log "══════════════════════════════════════════════════════════════════════"
if [ "$FINAL_EXIT" -eq 0 ]; then
  log "  ✅ DEV DLT Integration Test PASSED  (elapsed=${ELAPSED}s)"
else
  log "  ❌ DEV DLT Integration Test FAILED  (elapsed=${ELAPSED}s)"
  [ "$VALIDATION_EXIT" -ne 0 ] && log "     → Gold MV validation failed (Step 5)"
  [ "$LAMBDA_EXIT"     -ne 0 ] && log "     → Lambda chain failed (Step 6 — CONSUMPTION items missing)"
fi
log "══════════════════════════════════════════════════════════════════════"

exit "$FINAL_EXIT"
