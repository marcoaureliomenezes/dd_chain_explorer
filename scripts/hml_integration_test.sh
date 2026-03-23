#!/usr/bin/env bash
# =============================================================================
# HML Integration Test — onchain-stream-txs
#
# Validates that all peripheral AWS services receive data after ECS containers
# start. Phases run sequentially with fail-fast: any failure in a phase stops
# execution immediately, avoiding wasted timeout burns on downstream phases.
#
# Phases:
#   0 — ECS task health check (≥1 task RUNNING)
#   1 — CloudWatch log events per ECS service (proves containers are logging)
#   2 — SQS NumberOfMessagesSent > 0
#   3 — Kinesis IncomingRecords > 0
#   4 — DynamoDB items written
#   5 — Firehose delivery streams ACTIVE
#   6 — S3 .gz files delivered by Firehose
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

CLOUDWATCH_LOG_GROUP="${CLOUDWATCH_LOG_GROUP:-/apps/dm-chain-explorer-${ENV}}"
# shellcheck disable=SC2089
ECS_SERVICES="dm-mined-blocks-watcher dm-orphan-blocks-watcher dm-block-data-crawler dm-mined-txs-crawler dm-txs-input-decoder"

# Timeout (seconds) for each phase
WAIT_LOGS_SECS="${WAIT_LOGS_SECS:-60}"        # Phase 1 — CW log events per service
WAIT_PHASE1_SECS="${WAIT_PHASE1_SECS:-120}"   # Phase 2 — SQS (anchored to SCRIPT_START; CloudWatch may lag 1-2 min)
WAIT_KINESIS_SECS="${WAIT_KINESIS_SECS:-300}"  # Phase 3 — Kinesis (multi-hop chain + CW ingest delay)
WAIT_DYNAMODB_SECS="${WAIT_DYNAMODB_SECS:-120}" # Phase 4 — DynamoDB
WAIT_PHASE2_SECS="${WAIT_PHASE2_SECS:-120}"   # Phases 5-6 — Firehose + S3

POLL_INTERVAL=15     # seconds between retries (SQS/Kinesis/DynamoDB/S3)
LOG_POLL_INTERVAL=10 # seconds between retries (CW log events)

# ── Counters ──────────────────────────────────────────────────────────────────
PASS=0
FAIL=0
SCRIPT_START=$(date +%s)

# ── Utilities ─────────────────────────────────────────────────────────────────
log()  { echo "[$(date -u '+%H:%M:%S')] $*"; }
ok()   { log "✅ PASS — $*"; PASS=$((PASS + 1)); }
fail() { log "❌ FAIL — $*"; FAIL=$((FAIL + 1)); }

# fail_fast <phase_label> — exits immediately if any FAIL has been recorded
fail_fast() {
  if [ "$FAIL" -gt 0 ]; then
    log ""
    log "💥 $1: ${FAIL} check(s) failed — parando execução (fail-fast)"
    exit 1
  fi
}

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

# cw_sum_since <namespace> <metric> <dim_name> <dim_value> <epoch_start>
# Returns the SUM of a CloudWatch metric from a fixed epoch timestamp to now.
# Used to prevent false-positives from carry-over data of previous CI runs.
cw_sum_since() {
  local ns="$1" metric="$2" dn="$3" dv="$4" epoch_start="$5"
  local end; end=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  local start; start=$(date -u -d "@${epoch_start}" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null \
    || date -u -r "${epoch_start}" +%Y-%m-%dT%H:%M:%SZ)  # macOS fallback
  local win; win=$(( $(date +%s) - epoch_start + 1 ))
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
log "  CLOUDWATCH_LOG_GROUP=${CLOUDWATCH_LOG_GROUP}"
log "══════════════════════════════════════════════════════════════════════"

# =============================================================================
# Phase 0 — ECS task health check
# =============================================================================
if [ -n "${HML_ECS_CLUSTER:-}" ]; then
  log ""; log "──── Phase 0: ECS task health check ────"; log ""
  RUNNING=$(aws ecs list-tasks --cluster "$HML_ECS_CLUSTER" --desired-status RUNNING \
    --query 'length(taskArns)' --output text --region "$REGION" 2>/dev/null || echo "0")
  if [ "${RUNNING:-0}" -ge 1 ]; then
    ok "ECS cluster ${HML_ECS_CLUSTER} — ${RUNNING} task(s) RUNNING"
  else
    fail "ECS cluster ${HML_ECS_CLUSTER} — 0 tasks RUNNING (containers didn't start)"
  fi
fi
fail_fast "Phase 0 — ECS task health check"

# =============================================================================
# Phase 1 — CloudWatch Logs per ECS service
# Proves each container is running and emitting logs. Uses a 5-minute look-back
# window so that containers started before this script still pass.
# Log stream prefix convention: <service-name>/<container-name>/<task-id>
# =============================================================================
log ""; log "──── Phase 1: CloudWatch Logs per ECS service  (timeout=${WAIT_LOGS_SECS}s each) ────"; log ""
LOOK_START_MS=$(( ($(date +%s) - 300) * 1000 ))
# shellcheck disable=SC2090
for SVC in $ECS_SERVICES; do
  log "⏳ CW Logs ${SVC} — checking for log events in the last 5 min ..."
  DEADLINE=$(( $(date +%s) + WAIT_LOGS_SECS ))
  FOUND=false
  while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    EVENTS=$(aws logs filter-log-events \
      --log-group-name        "$CLOUDWATCH_LOG_GROUP" \
      --log-stream-name-prefix "${SVC}/" \
      --start-time             "$LOOK_START_MS" \
      --limit                  1 \
      --query                  'length(events)' \
      --output text --region   "$REGION" 2>/dev/null || echo "0")
    if [ "${EVENTS:-0}" -ge 1 ] 2>/dev/null; then
      ok "CW Logs ${SVC} — ${EVENTS} event(s) found"
      FOUND=true
      break
    fi
    log "   → no log events yet, retrying in ${LOG_POLL_INTERVAL}s ..."
    sleep "$LOG_POLL_INTERVAL"
  done
  $FOUND || fail "CW Logs ${SVC} — no log events found after ${WAIT_LOGS_SECS}s"
done
fail_fast "Phase 1 — ECS container logs"

# =============================================================================
# Phase 2 — SQS
# Uses SCRIPT_START as the lower bound so that messages sent by a previous CI
# run sharing the same queue names do not cause false-positives.
# =============================================================================
log ""; log "──── Phase 2: SQS  (timeout=${WAIT_PHASE1_SECS}s) ────"; log ""
for QUEUE in "$SQS_QUEUE_MINED_BLOCKS" "$SQS_QUEUE_TXS_HASH_IDS"; do
  log "⏳ SQS ${QUEUE} — polling CloudWatch NumberOfMessagesSent ..."
  DEADLINE=$(( $(date +%s) + WAIT_PHASE1_SECS ))
  FOUND=false
  while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    VAL=$(cw_sum_since "AWS/SQS" "NumberOfMessagesSent" "QueueName" "$QUEUE" "$SCRIPT_START")
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
fail_fast "Phase 2 — SQS"

# =============================================================================
# Phase 3 — Kinesis
# Uses SCRIPT_START as the lower bound of the CW query window so that data from
# previous CI runs sharing the same stream names do not cause false-positives.
# =============================================================================
log ""; log "──── Phase 3: Kinesis  (timeout=${WAIT_KINESIS_SECS}s) ────"; log ""
for STREAM in "$KINESIS_STREAM_BLOCKS" "$KINESIS_STREAM_TRANSACTIONS" "$KINESIS_STREAM_DECODED"; do
  log "⏳ Kinesis ${STREAM} — polling CloudWatch IncomingRecords ..."
  DEADLINE=$(( $(date +%s) + WAIT_KINESIS_SECS ))
  FOUND=false
  while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    VAL=$(cw_sum_since "AWS/Kinesis" "IncomingRecords" "StreamName" "$STREAM" "$SCRIPT_START")
    if is_positive "$VAL" 2>/dev/null; then
      ok "Kinesis ${STREAM} — IncomingRecords=$(printf '%.0f' "$VAL")"
      FOUND=true
      break
    fi
    log "   → not yet (value=${VAL}), retrying in ${POLL_INTERVAL}s ..."
    sleep "$POLL_INTERVAL"
  done
  $FOUND || fail "Kinesis ${STREAM} — no IncomingRecords within ${WAIT_KINESIS_SECS}s"
done
fail_fast "Phase 3 — Kinesis"

# =============================================================================
# Phase 4 — DynamoDB
# =============================================================================
log ""; log "──── Phase 4: DynamoDB  (timeout=${WAIT_DYNAMODB_SECS}s) ────"; log ""
log "⏳ DynamoDB ${DYNAMODB_TABLE} — polling for items ..."
DEADLINE=$(( $(date +%s) + WAIT_DYNAMODB_SECS ))
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
$FOUND || fail "DynamoDB ${DYNAMODB_TABLE} — no items within ${WAIT_DYNAMODB_SECS}s"
fail_fast "Phase 4 — DynamoDB"

# =============================================================================
# Phase 5 — Firehose status
# Firehose streams must be ACTIVE before they can deliver data to S3.
# =============================================================================
log ""; log "──── Phase 5: Firehose  (timeout=${WAIT_PHASE2_SECS}s) ────"; log ""
for FH in \
  "firehose-mainnet-blocks-data-${ENV}" \
  "firehose-mainnet-transactions-data-${ENV}" \
  "firehose-mainnet-transactions-decoded-${ENV}"
do
  log "⏳ Firehose ${FH} — waiting for ACTIVE status ..."
  DEADLINE=$(( $(date +%s) + WAIT_PHASE2_SECS ))
  FH_STATUS="NOT_FOUND"
  FOUND=false
  while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    FH_STATUS=$(aws firehose describe-delivery-stream \
      --region               "$REGION" \
      --delivery-stream-name "$FH" \
      --query  'DeliveryStreamDescription.DeliveryStreamStatus' \
      --output text 2>/dev/null || echo "NOT_FOUND")
    if [ "$FH_STATUS" = "ACTIVE" ]; then
      ok "Firehose ${FH} — status=ACTIVE"
      FOUND=true
      break
    fi
    log "   → status=${FH_STATUS}, retrying in ${POLL_INTERVAL}s ..."
    sleep "$POLL_INTERVAL"
  done
  $FOUND || fail "Firehose ${FH} — status=${FH_STATUS} after ${WAIT_PHASE2_SECS}s (expected ACTIVE)"
done
fail_fast "Phase 5 — Firehose"

# =============================================================================
# Phase 6 — S3 delivery
# Firehose buffers data from Kinesis and flushes to S3 (buffer 60s / 1MB).
# Expected: .gz files appear under s3://<bucket>/raw/<stream>/year=.../
# =============================================================================
log ""; log "──── Phase 6: S3 Firehose delivery  (timeout=${WAIT_PHASE2_SECS}s) ────"; log ""
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
