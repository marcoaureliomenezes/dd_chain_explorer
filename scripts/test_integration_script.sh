#!/usr/bin/env bash
# =============================================================================
# Test Suite — Integration Test Scripts
#
# Compares original vs optimized integration test scripts on DEV environment.
# Safe to run locally — no production impact.
#
# Usage:
#   bash scripts/test_integration_script.sh [original|optimized|both]
#
# Examples:
#   bash scripts/test_integration_script.sh original   # Test old script
#   bash scripts/test_integration_script.sh optimized  # Test new script
#   bash scripts/test_integration_script.sh both       # Compare both
#
# =============================================================================
set -euo pipefail

MODE="${1:-both}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# ── Configuration for DEV environment ──────────────────────────────────────
export ENV="dev"
export REGION="sa-east-1"
export S3_BUCKET="dm-chain-explorer-dev-ingestion"
export DYNAMODB_TABLE="dm-chain-explorer-dev"
export KINESIS_STREAM_TRANSACTIONS="mainnet-transactions-data-dev"
export FIREHOSE_STREAM_BLOCKS="firehose-mainnet-blocks-data-dev"
export FIREHOSE_STREAM_DECODED="firehose-mainnet-transactions-decoded-dev"
export SQS_QUEUE_MINED_BLOCKS="mainnet-mined-blocks-events-dev"
export SQS_QUEUE_TXS_HASH_IDS="mainnet-block-txs-hash-id-dev"
export CLOUDWATCH_LOG_GROUP="/apps/dm-chain-explorer-dev"

# Optional: override defaults for faster testing
export WAIT_LOGS_SECS="${WAIT_LOGS_SECS:-30}"
export WAIT_PHASE1_SECS="${WAIT_PHASE1_SECS:-60}"
export WAIT_KINESIS_SECS="${WAIT_KINESIS_SECS:-60}"
export WAIT_DYNAMODB_SECS="${WAIT_DYNAMODB_SECS:-30}"
export WAIT_PHASE2_SECS="${WAIT_PHASE2_SECS:-60}"

# ── Colors for terminal output ─────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() { echo -e "${BLUE}[TEST]${NC} $*"; }
ok()  { echo -e "${GREEN}✅ PASS${NC} $*"; }
fail() { echo -e "${RED}❌ FAIL${NC} $*"; }
warn() { echo -e "${YELLOW}⚠️  WARN${NC} $*"; }

# ── Validate environment ───────────────────────────────────────────────────
validate_env() {
  log "Validating AWS/Databricks credentials..."

  if ! aws sts get-caller-identity > /dev/null 2>&1; then
    fail "AWS credentials not configured. Run: aws configure"
    return 1
  fi

  if ! command -v databricks &> /dev/null; then
    warn "databricks CLI not found (optional for DEV test)"
  fi

  ok "Environment validated"
  return 0
}

# ── Run integration test script ─────────────────────────────────────────────
run_test() {
  local script="$1"
  local test_name="$2"
  local log_file="/tmp/test_integration_${test_name}.log"

  log ""
  log "════════════════════════════════════════════════════════════════════"
  log "Running: $test_name"
  log "Script: $script"
  log "Timeout: WAIT_PHASE1_SECS=${WAIT_PHASE1_SECS}s"
  log "════════════════════════════════════════════════════════════════════"
  log ""

  local start=$(date +%s)

  if bash "$script" 2>&1 | tee "$log_file"; then
    local elapsed=$(( $(date +%s) - start ))
    ok "$test_name passed in ${elapsed}s"
    echo "$elapsed" > "/tmp/test_integration_${test_name}.elapsed"
    return 0
  else
    local elapsed=$(( $(date +%s) - start ))
    fail "$test_name failed after ${elapsed}s"
    echo "------- Last 50 lines of log -------"
    tail -50 "$log_file"
    echo "------- End of log -------"
    return 1
  fi
}

# ── Compare results ────────────────────────────────────────────────────────
compare_results() {
  log ""
  log "════════════════════════════════════════════════════════════════════"
  log "Comparison Results"
  log "════════════════════════════════════════════════════════════════════"
  log ""

  if [ -f /tmp/test_integration_original.elapsed ] && [ -f /tmp/test_integration_optimized.elapsed ]; then
    local orig=$(cat /tmp/test_integration_original.elapsed)
    local opt=$(cat /tmp/test_integration_optimized.elapsed)
    local reduction=$(( orig - opt ))
    local percent=$(( reduction * 100 / orig ))

    log "Original script:  ${orig}s"
    log "Optimized script: ${opt}s"
    log "Reduction:       ${reduction}s (${percent}%)"

    if [ "$opt" -lt "$orig" ]; then
      ok "Optimized script is faster! 🚀"
    else
      warn "Optimized script is slower (may be transient)"
    fi
  fi

  log ""
}

# ── Main ──────────────────────────────────────────────────────────────────
main() {
  log "DEV Integration Test Suite"
  log "Testing scripts from: $PROJECT_DIR/scripts/"
  log ""

  if ! validate_env; then
    exit 1
  fi

  case "$MODE" in
    original)
      run_test "$SCRIPT_DIR/hml_integration_test.sh" "original" || exit 1
      ;;
    optimized)
      run_test "$SCRIPT_DIR/hml_integration_test_optimized.sh" "optimized" || exit 1
      ;;
    both)
      log "Running BOTH scripts for comparison..."
      local orig_ok=true
      local opt_ok=true

      run_test "$SCRIPT_DIR/hml_integration_test.sh" "original" || orig_ok=false
      run_test "$SCRIPT_DIR/hml_integration_test_optimized.sh" "optimized" || opt_ok=false

      compare_results

      if [ "$orig_ok" = true ] && [ "$opt_ok" = true ]; then
        ok "Both scripts passed! ✅"
        exit 0
      elif [ "$opt_ok" = true ]; then
        ok "Optimized script passed (original failed) ✅"
        exit 0
      else
        fail "At least one script failed ❌"
        exit 1
      fi
      ;;
    *)
      echo "Usage: $0 [original|optimized|both]"
      exit 1
      ;;
  esac

  ok "Test complete!"
}

main
