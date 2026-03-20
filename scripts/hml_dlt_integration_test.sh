#!/usr/bin/env bash
# =============================================================================
# HML DLT Integration Test — Gold Materialized Views Validation
#
# Validates that all mandatory Gold MVs produced by the DLT pipelines
# (dm-ethereum + dm-app-logs) contain data after pipeline execution.
#
# This script is VALIDATION ONLY — pipeline deploy and trigger are done
# as separate steps (workflow or manual).
#
# Prerequisites:
#   • DLT pipelines already triggered and completed
#   • Databricks SQL Warehouse running (Free Edition serverless)
#   • DATABRICKS_HOST and DATABRICKS_TOKEN env vars set
#
# Usage (DEV — local validation):
#   DATABRICKS_HOST=https://dbc-409f1007-5779.cloud.databricks.com \
#   DATABRICKS_TOKEN=<pat> \
#   CATALOG=dev \
#   WAREHOUSE_ID=a2a66f2adb0faf18 \
#   bash scripts/hml_dlt_integration_test.sh
#
# Usage (HML — CI/CD):
#   Env vars injected by the workflow step.
#
# =============================================================================
set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
DATABRICKS_HOST="${DATABRICKS_HOST:?DATABRICKS_HOST is required}"
DATABRICKS_TOKEN="${DATABRICKS_TOKEN:?DATABRICKS_TOKEN is required}"
CATALOG="${CATALOG:-hml}"
WAREHOUSE_ID="${WAREHOUSE_ID:?WAREHOUSE_ID is required}"

# Poll settings for SQL statement completion
SQL_POLL_INTERVAL=5    # seconds between polls
SQL_TIMEOUT=120        # max seconds to wait per statement

# ── Mandatory Gold MVs ────────────────────────────────────────────────────────
# Format: "schema.table"
# pipeline_ethereum (dm-ethereum)
GOLD_MVS_ETHEREUM=(
  "s_apps.popular_contracts_ranking"
  "s_apps.peer_to_peer_txs"
  "s_apps.ethereum_gas_consume"
  "g_network.network_metrics_hourly"
)

# pipeline_app_logs (dm-app-logs)
GOLD_MVS_APP_LOGS=(
  "g_api_keys.etherscan_consumption"
  "g_api_keys.web3_keys_consumption"
)

# Skipped (batch dependency — TODO)
GOLD_MVS_SKIP=(
  "s_apps.transactions_lambda"
)

# ── Counters ──────────────────────────────────────────────────────────────────
PASS=0
FAIL=0
SKIP=0
SCRIPT_START=$(date +%s)

# ── Utilities ─────────────────────────────────────────────────────────────────
log()  { echo "[$(date -u '+%H:%M:%S')] $*"; }
ok()   { log "✅ PASS — $*"; PASS=$((PASS + 1)); }
fail() { log "❌ FAIL — $*"; FAIL=$((FAIL + 1)); }
skip() { log "⏭️  SKIP — $*"; SKIP=$((SKIP + 1)); }

# ── Databricks SQL Statement Execution API ────────────────────────────────────
# Submits a SQL statement and waits for the result.
# Returns the first row/first column value (the COUNT(*)).
db_sql_count() {
  local fqn="$1"  # e.g. dev.s_apps.popular_contracts_ranking
  local stmt="SELECT COUNT(*) AS cnt FROM \`${CATALOG}\`.${fqn}"

  # Submit statement
  local response
  response=$(curl -s -X POST \
    "${DATABRICKS_HOST}/api/2.0/sql/statements/" \
    -H "Authorization: Bearer ${DATABRICKS_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "$(jq -n \
      --arg stmt "$stmt" \
      --arg wid  "$WAREHOUSE_ID" \
      '{
        statement: $stmt,
        warehouse_id: $wid,
        wait_timeout: "0s"
      }')")

  local stmt_id
  stmt_id=$(echo "$response" | jq -r '.statement_id // empty')
  if [ -z "$stmt_id" ]; then
    log "    ERROR: failed to submit SQL statement for ${fqn}"
    log "    Response: $(echo "$response" | jq -c .)"
    echo "-1"
    return
  fi

  # Poll for completion
  local deadline=$(( $(date +%s) + SQL_TIMEOUT ))
  local status="PENDING"
  local poll_response

  while [ "$(date +%s)" -lt "$deadline" ]; do
    poll_response=$(curl -s -X GET \
      "${DATABRICKS_HOST}/api/2.0/sql/statements/${stmt_id}" \
      -H "Authorization: Bearer ${DATABRICKS_TOKEN}")

    status=$(echo "$poll_response" | jq -r '.status.state // "PENDING"')

    case "$status" in
      SUCCEEDED)
        local cnt
        cnt=$(echo "$poll_response" | jq -r '.result.data_array[0][0] // "0"')
        echo "$cnt"
        return
        ;;
      FAILED|CANCELED|CLOSED)
        local err_msg
        err_msg=$(echo "$poll_response" | jq -r '.status.error.message // "unknown error"')
        log "    ERROR: SQL statement ${status} for ${fqn}: ${err_msg}"
        echo "-1"
        return
        ;;
      *)
        sleep "$SQL_POLL_INTERVAL"
        ;;
    esac
  done

  log "    ERROR: SQL statement timed out after ${SQL_TIMEOUT}s for ${fqn}"
  echo "-1"
}

# =============================================================================
log "══════════════════════════════════════════════════════════════════════"
log "  DLT Integration Test — Gold MVs Validation"
log "  CATALOG=${CATALOG}   WAREHOUSE_ID=${WAREHOUSE_ID}"
log "  DATABRICKS_HOST=${DATABRICKS_HOST}"
log "══════════════════════════════════════════════════════════════════════"
log ""

# ── Validate pipeline_ethereum Gold MVs ───────────────────────────────────────
log "──── Pipeline: dm-ethereum ────"
log ""

for MV in "${GOLD_MVS_ETHEREUM[@]}"; do
  log "⏳ Checking ${CATALOG}.${MV} ..."
  COUNT=$(db_sql_count "$MV")
  if [ "$COUNT" = "-1" ]; then
    fail "${CATALOG}.${MV} — query error (table may not exist)"
  elif [ "$COUNT" -gt 0 ] 2>/dev/null; then
    ok "${CATALOG}.${MV} — row_count=${COUNT}"
  else
    fail "${CATALOG}.${MV} — row_count=0 (expected > 0)"
  fi
done

log ""

# ── Validate pipeline_app_logs Gold MVs ───────────────────────────────────────
log "──── Pipeline: dm-app-logs ────"
log ""

for MV in "${GOLD_MVS_APP_LOGS[@]}"; do
  log "⏳ Checking ${CATALOG}.${MV} ..."
  COUNT=$(db_sql_count "$MV")
  if [ "$COUNT" = "-1" ]; then
    fail "${CATALOG}.${MV} — query error (table may not exist)"
  elif [ "$COUNT" -gt 0 ] 2>/dev/null; then
    ok "${CATALOG}.${MV} — row_count=${COUNT}"
  else
    fail "${CATALOG}.${MV} — row_count=0 (expected > 0)"
  fi
done

log ""

# ── Skipped MVs (batch dependency) ────────────────────────────────────────────
log "──── Skipped (TODO — batch popular contracts flow) ────"
log ""

for MV in "${GOLD_MVS_SKIP[@]}"; do
  skip "${CATALOG}.${MV} — depends on batch popular_contracts_txs pipeline (not yet tested)"
done

# =============================================================================
# Summary
# =============================================================================
ELAPSED=$(( $(date +%s) - SCRIPT_START ))
log ""
log "══════════════════════════════════════════════════════════════════════"
log "  Results: PASS=${PASS}  FAIL=${FAIL}  SKIP=${SKIP}  elapsed=${ELAPSED}s"
log "══════════════════════════════════════════════════════════════════════"

# TODO: Batch Popular Contracts Integration Test
# ───────────────────────────────────────────────
# The full batch flow is:
#   1. DLT Gold MV `popular_contracts_ranking` → top 100 contracts
#   2. Periodic workflow exports ranking to DynamoDB (via Lambda)
#   3. Another Lambda reads DynamoDB contracts → fetches txs from Etherscan API
#   4. Lambda writes batch txs to S3 (raw bucket)
#   5. DLT reads from S3 → `b_ethereum.popular_contracts_txs` (Bronze)
#   6. Gold MV `transactions_lambda` JOINs streaming + batch data
#
# This requires: Lambda functions, Etherscan API keys, DynamoDB orchestration.
# Deferred to a dedicated integration test in a future iteration.

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
exit 0
