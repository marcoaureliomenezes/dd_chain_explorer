#!/usr/bin/env bash
# =============================================================================
# HML Integration Test — onchain-stream-txs
#
# Validates that all peripheral AWS services receive data after ECS containers
# start. Designed to mirror the healthy DEV baseline observed on 2026-03-19:
#   • SQS: both queues processing messages in real-time (0 visible = healthy)
#   • Kinesis: all 3 streams ACTIVE, receiving records
#   • DynamoDB: BLOCK_CACHE items written by containers
#   • Firehose: all delivery streams ACTIVE
#   • S3: .gz files delivered to raw/ by Firehose
#
# Usage (HML — default):
#   bash scripts/hml_integration_test.sh
#
# Usage (DEV — for local validation):
#   ENV=dev \
#   S3_BUCKET=dm-chain-explorer-dev-ingestion \
#   DYNAMODB_TABLE=dm-chain-explorer \
#   bash scripts/hml_integration_test.sh
#
# All variables have sensible defaults for HML. Override as needed.
# =============================================================================
set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
ENV="${ENV:-hml}"
REGION="${REGION:-sa-east-1}"
S3_BUCKET="${S3_BUCKET:-dm-chain-explorer-${ENV}-ingestion}"
DYNAMODB_TABLE="${DYNAMODB_TABLE:-dm-chain-explorer-${ENV}}"

KINESIS_STREAM_BLOCKS="${KINESIS_STREAM_BLOCKS:-mainnet-blocks-data-${ENV}}"
KINESIS_STREAM_TRANSACTIONS="${KINESIS_STREAM_TRANSACTIONS:-mainnet-transactions-data-${ENV}}"
KINESIS_STREAM_DECODED="${KINESIS_STREAM_DECODED:-mainnet-transactions-decoded-${ENV}}"

SQS_QUEUE_MINED_BLOCKS="${SQS_QUEUE_MINED_BLOCKS:-mainnet-mined-blocks-events-${ENV}}"
SQS_QUEUE_TXS_HASH_IDS="${SQS_QUEUE_TXS_HASH_IDS:-mainnet-block-txs-hash-id-${ENV}}"

# Timeout (seconds) for each phase
WAIT_PHASE1_SECS="${WAIT_PHASE1_SECS:-180}"   # SQS + Kinesis + DynamoDB
WAIT_PHASE2_SECS="${WAIT_PHASE2_SECS:-480}"   # Firehose + S3

POLL_INTERVAL=15   # seconds between retries

# ── Counters ──────────────────────────────────────────────────────────────────
PASS=0
FAIL=0
SCRIPT_START=$(date +%s)

# ── Utilities ─────────────────────────────────────────────────────────────────
log()  { echo "[$(date -u '+%H:%M:%S')] $*"; }
ok()   { log "✅ PASS — $*"; PASS=$((PASS + 1)); }
fail() { log "❌ FAIL — $*"; FAIL=$((FAIL + 1)); }

# cw_sum <namespace> <metric> <dim_name> <dim_value> [window_secs=300]
# Returns the SUM of a CloudWatch metric over the last <window_secs>.
cw_sum() {
  local ns="$1" metric="$2" dn="$3" dv="$4" win="${5:-300}"
  local end; end=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  local start; start=$(date -u -d "-${win} seconds" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null \
    || date -u -v-${win}S +%Y-%m-%dT%H:%M:%SZ)  # macOS fallback
  aws cloudwatch get-metric-statistics \
    --region    "$REGION"  \
    --namespace "$ns"      \
    --metric-name "$metric" \
    --dimensions "Name=${dn},Value=${dv}" \
    --start-time "$start"  \
    --end-time   "$end"    \
    --period     "$win"    \
    --statistics Sum       \
    --query 'Datapoints[0].Sum' \
    --output text 2>/dev/null || echo "None"
}

# is_positive <value> — returns 0 if value is a number > 0
is_positive() {
  local v="$1"
  [[ "$v" =~ ^[0-9]+(\.[0-9]+)?$ ]] && awk "BEGIN{exit !($v > 0)}"
}

# s3_new_gz_file <bucket> <prefix> <minutes_ago>
# Returns the S3 key of the first .gz file newer than <minutes_ago> minutes.
s3_new_gz_file() {
  local bucket="$1" prefix="$2" minutes_ago="${3:-10}"
  # NOTE: python3 -c is used (not heredoc) so sys.stdin can read from the pipe.
  # aws s3 ls timestamps are in LOCAL timezone; datetime.now() matches that.
  aws s3 ls "s3://${bucket}/${prefix}" --recursive 2>/dev/null \
    | python3 -c "
import sys, datetime
cutoff = datetime.datetime.now() - datetime.timedelta(minutes=${minutes_ago})
for line in sys.stdin:
    parts = line.split()
    if len(parts) >= 4 and parts[3].endswith('.gz'):
        try:
            ts = datetime.datetime.strptime(parts[0] + ' ' + parts[1], '%Y-%m-%d %H:%M:%S')
            if ts >= cutoff:
                print(parts[3])
                sys.exit(0)
        except Exception:
            pass
"
}

# =============================================================================
log "══════════════════════════════════════════════════════════════════════"
log "  HML Integration Test   ENV=${ENV}   REGION=${REGION}"
log "  S3_BUCKET=${S3_BUCKET}"
log "  DYNAMODB_TABLE=${DYNAMODB_TABLE}"
log "══════════════════════════════════════════════════════════════════════"

# =============================================================================
# Phase 1 — SQS + Kinesis + DynamoDB
# Expected behaviour from DEV baseline:
#   • SQS queues stay near-empty (consumers keep up) but NumberOfMessagesSent > 0
#   • Kinesis IncomingRecords > 0 as containers push blocks/txs
#   • DynamoDB accumulates BLOCK_CACHE items written by orphan-blocks-watcher
# =============================================================================
log ""
log "──── Phase 1: SQS / Kinesis / DynamoDB  (timeout=${WAIT_PHASE1_SECS}s) ────"
log ""

# ── Check 1: SQS NumberOfMessagesSent > 0 ─────────────────────────────────────
for QUEUE in "$SQS_QUEUE_MINED_BLOCKS" "$SQS_QUEUE_TXS_HASH_IDS"; do
  log "⏳ SQS ${QUEUE} — polling CloudWatch NumberOfMessagesSent ..."
  DEADLINE=$(( $(date +%s) + WAIT_PHASE1_SECS ))
  FOUND=false
  while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    VAL=$(cw_sum "AWS/SQS" "NumberOfMessagesSent" "QueueName" "$QUEUE" 300)
    if is_positive "$VAL" 2>/dev/null; then
      ok "SQS ${QUEUE} — NumberOfMessagesSent=$(printf '%.0f' "$VAL")"
      FOUND=true
      break
    fi
    log "   → not yet (value=${VAL}), retrying in ${POLL_INTERVAL}s ..."
    sleep "$POLL_INTERVAL"
  done
  $FOUND || fail "SQS ${QUEUE} — no messages sent within ${WAIT_PHASE1_SECS}s"
done

# ── Check 2: Kinesis IncomingRecords > 0 ──────────────────────────────────────
for STREAM in "$KINESIS_STREAM_BLOCKS" "$KINESIS_STREAM_TRANSACTIONS" "$KINESIS_STREAM_DECODED"; do
  log "⏳ Kinesis ${STREAM} — polling CloudWatch IncomingRecords ..."
  DEADLINE=$(( $(date +%s) + WAIT_PHASE1_SECS ))
  FOUND=false
  while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    VAL=$(cw_sum "AWS/Kinesis" "IncomingRecords" "StreamName" "$STREAM" 300)
    if is_positive "$VAL" 2>/dev/null; then
      ok "Kinesis ${STREAM} — IncomingRecords=$(printf '%.0f' "$VAL")"
      FOUND=true
      break
    fi
    log "   → not yet (value=${VAL}), retrying in ${POLL_INTERVAL}s ..."
    sleep "$POLL_INTERVAL"
  done
  $FOUND || fail "Kinesis ${STREAM} — no IncomingRecords within ${WAIT_PHASE1_SECS}s"
done

# ── Check 3: DynamoDB — at least 1 item written ───────────────────────────────
log "⏳ DynamoDB ${DYNAMODB_TABLE} — polling for items ..."
DEADLINE=$(( $(date +%s) + WAIT_PHASE1_SECS ))
FOUND=false
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  COUNT=$(aws dynamodb scan \
    --region     "$REGION" \
    --table-name "$DYNAMODB_TABLE" \
    --select     COUNT \
    --limit      1 \
    --query      'Count' \
    --output     text 2>/dev/null || echo "0")
  if [ "${COUNT:-0}" -ge 1 ] 2>/dev/null; then
    ok "DynamoDB ${DYNAMODB_TABLE} — scan returned Count=${COUNT}"
    FOUND=true
    break
  fi
  log "   → not yet (Count=${COUNT}), retrying in ${POLL_INTERVAL}s ..."
  sleep "$POLL_INTERVAL"
done
$FOUND || fail "DynamoDB ${DYNAMODB_TABLE} — no items within ${WAIT_PHASE1_SECS}s"

# =============================================================================
# Phase 2 — Firehose status + S3 delivery
# Firehose buffers data from Kinesis and flushes to S3 (buffer 60s / 1MB).
# Expected: files appear under s3://<bucket>/raw/<stream>/year=.../
# =============================================================================
log ""
log "──── Phase 2: Firehose / S3 delivery  (timeout=${WAIT_PHASE2_SECS}s) ────"
log ""

# ── Check 4: Firehose delivery streams ACTIVE ─────────────────────────────────
for FH in \
  "firehose-mainnet-blocks-data-${ENV}" \
  "firehose-mainnet-transactions-data-${ENV}" \
  "firehose-mainnet-transactions-decoded-${ENV}"
do
  STATUS=$(aws firehose describe-delivery-stream \
    --region               "$REGION" \
    --delivery-stream-name "$FH" \
    --query  'DeliveryStreamDescription.DeliveryStreamStatus' \
    --output text 2>/dev/null || echo "NOT_FOUND")
  if [ "$STATUS" = "ACTIVE" ]; then
    ok "Firehose ${FH} — status=ACTIVE"
  else
    fail "Firehose ${FH} — status=${STATUS} (expected ACTIVE)"
  fi
done

# ── Check 5: S3 — ≥1 .gz file delivered to raw/ within last 10 minutes ─────
# Each Kinesis stream has its own prefix; check at least the blocks stream.
for STREAM_PREFIX in \
  "raw/mainnet-blocks-data/" \
  "raw/mainnet-transactions-data/" \
  "raw/mainnet-transactions-decoded/"
do
  log "⏳ S3 s3://${S3_BUCKET}/${STREAM_PREFIX} — waiting for Firehose delivery ..."
  DEADLINE=$(( $(date +%s) + WAIT_PHASE2_SECS ))
  FOUND=false
  while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    NEW_FILE=$(s3_new_gz_file "$S3_BUCKET" "$STREAM_PREFIX" 10 || true)
    if [ -n "$NEW_FILE" ]; then
      ok "S3 ${STREAM_PREFIX} — file delivered: ${NEW_FILE}"
      FOUND=true
      break
    fi
    REMAINING=$(( DEADLINE - $(date +%s) ))
    log "   → no new file yet, retrying in ${POLL_INTERVAL}s (${REMAINING}s remaining) ..."
    sleep "$POLL_INTERVAL"
  done
  $FOUND || fail "S3 ${S3_BUCKET}/${STREAM_PREFIX} — no .gz file in last 10 min after ${WAIT_PHASE2_SECS}s"
done

# =============================================================================
# Summary
# =============================================================================
ELAPSED=$(( $(date +%s) - SCRIPT_START ))
log ""
log "══════════════════════════════════════════════════════════════════════"
log "  Results: PASS=${PASS}  FAIL=${FAIL}  elapsed=${ELAPSED}s"
log "══════════════════════════════════════════════════════════════════════"

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
exit 0
