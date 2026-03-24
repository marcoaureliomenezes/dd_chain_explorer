#!/usr/bin/env bash
# =============================================================================
# DEV Integration Test — onchain-stream-txs (Docker Compose)
#
# Validates that all peripheral AWS services receive data after local Docker
# Compose containers start. Analogous to hml_integration_test.sh but adapted
# for the DEV environment where containers run via Docker Compose (not ECS).
#
# Phases run sequentially with fail-fast: any failure stops execution.
#
# Phases:
#   0 — Docker Compose container health check (replaces ECS task check)
#   1 — CloudWatch log events (proves containers are logging to AWS)
#   2 — SQS NumberOfMessagesSent > 0 (fast-path API + slow-path CloudWatch)
#   3 — Kinesis IncomingRecords > 0  (CloudWatch; lag ~5 min — set WAIT_KINESIS_SECS >= 360)
#   4 — DynamoDB items written
#   5 — Firehose delivery streams ACTIVE
#   6 — S3 .gz files delivered by Firehose
#
# Usage (DEV — default):
#   bash scripts/dev_integration_test.sh
#
# Usage (custom overrides):
#   ENV=dev \
#   S3_BUCKET=dm-chain-explorer-dev-ingestion \
#   DYNAMODB_TABLE=dm-chain-explorer \
#   bash scripts/dev_integration_test.sh
#
# All variables have sensible defaults for DEV. Override as needed.
# =============================================================================
set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
ENV="${ENV:-dev}"
REGION="${REGION:-sa-east-1}"
S3_BUCKET="${S3_BUCKET:-dm-chain-explorer-${ENV}-ingestion}"
DYNAMODB_TABLE="${DYNAMODB_TABLE:-dm-chain-explorer-dev}"

KINESIS_STREAM_BLOCKS="${KINESIS_STREAM_BLOCKS:-mainnet-blocks-data-${ENV}}"
KINESIS_STREAM_TRANSACTIONS="${KINESIS_STREAM_TRANSACTIONS:-mainnet-transactions-data-${ENV}}"
KINESIS_STREAM_DECODED="${KINESIS_STREAM_DECODED:-mainnet-transactions-decoded-${ENV}}"

SQS_QUEUE_MINED_BLOCKS="${SQS_QUEUE_MINED_BLOCKS:-mainnet-mined-blocks-events-${ENV}}"
SQS_QUEUE_TXS_HASH_IDS="${SQS_QUEUE_TXS_HASH_IDS:-mainnet-block-txs-hash-id-${ENV}}"

CLOUDWATCH_LOG_GROUP="${CLOUDWATCH_LOG_GROUP:-/apps/dm-chain-explorer-${ENV}}"
COMPOSE_FILE="${COMPOSE_FILE:-services/dev/00_compose/app_services.yml}"

# Docker Compose service names (used for health check)
# Replicas (transactions-crawler x6, txs-input-decoder x3) count as single services here
COMPOSE_CORE_SERVICES="python-job-mined-blocks-watcher python-job-orphan-blocks-watcher python-job-block-data-crawler"
COMPOSE_ALL_SERVICES="${COMPOSE_CORE_SERVICES} python-job-transactions-crawler python-job-txs-input-decoder"

# Minimum containers expected running (core 3 + at least 1 replica each for txs-crawler and decoder)
MIN_RUNNING="${MIN_RUNNING:-5}"

# Timeout (seconds) for each phase
WAIT_DOCKER_SECS="${WAIT_DOCKER_SECS:-90}"       # Phase 0 — Docker containers
WAIT_LOGS_SECS="${WAIT_LOGS_SECS:-120}"           # Phase 1 — CW log events
WAIT_SQS_SECS="${WAIT_SQS_SECS:-180}"             # Phase 2 — SQS
WAIT_KINESIS_SECS="${WAIT_KINESIS_SECS:-360}"     # Phase 3 — Kinesis (CW lag ~5 min)
WAIT_DYNAMODB_SECS="${WAIT_DYNAMODB_SECS:-180}"   # Phase 4 — DynamoDB
WAIT_PHASE2_SECS="${WAIT_PHASE2_SECS:-180}"       # Phases 5-6 — Firehose + S3

POLL_INTERVAL=15
LOG_POLL_INTERVAL=10

# ── Counters ──────────────────────────────────────────────────────────────────
PASS=0
FAIL=0
SCRIPT_START=$(date +%s)

# ── Utilities ─────────────────────────────────────────────────────────────────
log()  { echo "[$(date -u '+%H:%M:%S')] $*"; }
ok()   { log "✅ PASS — $*"; PASS=$((PASS + 1)); }
fail() { log "❌ FAIL — $*"; FAIL=$((FAIL + 1)); }
warn() { log "⚠️  WARN — $*"; }

fail_fast() {
  if [ "$FAIL" -gt 0 ]; then
    log ""
    log "💥 $1: ${FAIL} check(s) failed — parando execução (fail-fast)"
    log ""
    log "   Dicas de diagnóstico:"
    log "   • Docker logs: docker compose -f ${COMPOSE_FILE} logs --tail=30 <service>"
    log "   • Infra check: aws kinesis describe-stream-summary --stream-name mainnet-blocks-data-dev"
    log "   • CW Logs:     aws logs filter-log-events --log-group-name ${CLOUDWATCH_LOG_GROUP} --limit 5"
    exit 1
  fi
}

# cw_sum <namespace> <metric> <dim_name> <dim_value> [window_secs=300]
# Returns the SUM of a CloudWatch metric over the last <window_secs> (rolling).
cw_sum() {
  local ns="$1" metric="$2" dn="$3" dv="$4" win="${5:-300}"
  local end; end=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  local start; start=$(date -u -d "-${win} seconds" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null \
    || date -u -v-${win}S +%Y-%m-%dT%H:%M:%SZ)
  aws cloudwatch get-metric-statistics \
    --region      "$REGION"  \
    --namespace   "$ns"      \
    --metric-name "$metric"  \
    --dimensions  "Name=${dn},Value=${dv}" \
    --start-time  "$start"   \
    --end-time    "$end"     \
    --period      "$win"     \
    --statistics  Sum        \
    --query       'Datapoints[0].Sum' \
    --output      text 2>/dev/null || echo "None"
}

# cw_sum_since <namespace> <metric> <dim_name> <dim_value> <epoch_start>
# Returns the SUM of a CloudWatch metric from a fixed epoch timestamp to now.
# NOTE: AWS requires --period to be a multiple of 60; we ceil-round to satisfy this.
cw_sum_since() {
  local ns="$1" metric="$2" dn="$3" dv="$4" epoch_start="$5"
  local end; end=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  local start; start=$(date -u -d "@${epoch_start}" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null \
    || date -u -r "${epoch_start}" +%Y-%m-%dT%H:%M:%SZ)
  local win_raw; win_raw=$(( $(date +%s) - epoch_start + 1 ))
  local win; win=$(( ((win_raw + 59) / 60) * 60 ))  # ceil to nearest 60s (AWS API requirement)
  aws cloudwatch get-metric-statistics \
    --region      "$REGION"  \
    --namespace   "$ns"      \
    --metric-name "$metric"  \
    --dimensions  "Name=${dn},Value=${dv}" \
    --start-time  "$start"   \
    --end-time    "$end"     \
    --period      "$win"     \
    --statistics  Sum        \
    --query       'Datapoints[0].Sum' \
    --output      text 2>/dev/null || echo "None"
}

# is_positive <value> — returns 0 if value is a number > 0
is_positive() {
  local v="$1"
  [[ "$v" =~ ^[0-9]+(\.[0-9]+)?$ ]] && awk "BEGIN{exit !($v > 0)}"
}

# s3_new_gz_file <bucket> <prefix> <minutes_ago>
s3_new_gz_file() {
  local bucket="$1" prefix="$2" minutes_ago="${3:-10}"
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

# docker_running_count — conta containers em estado running para o compose file
docker_running_count() {
  (docker compose -f "$COMPOSE_FILE" ps --format json 2>/dev/null || true) \
    | python3 -c "
import sys, json
data = []
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        data.append(json.loads(line))
    except Exception:
        pass
running = sum(
    1 for c in data
    if 'running' in (c.get('State','') or c.get('Status','')).lower()
)
print(running)
" 2>/dev/null
}

# docker_crashed_list — lista serviços que crasharam (exited/restarting/dead)
docker_crashed_list() {
  (docker compose -f "$COMPOSE_FILE" ps --format json 2>/dev/null || true) \
    | python3 -c "
import sys, json
data = []
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        data.append(json.loads(line))
    except Exception:
        pass
for c in data:
    state = (c.get('State','') or c.get('Status','')).lower()
    if any(s in state for s in ('exit','restart','dead','error')):
        print(c.get('Name', c.get('Service','')))
" 2>/dev/null || true
}

# =============================================================================
log "══════════════════════════════════════════════════════════════════════"
log "  DEV Integration Test   ENV=${ENV}   REGION=${REGION}"
log "  S3_BUCKET=${S3_BUCKET}"
log "  DYNAMODB_TABLE=${DYNAMODB_TABLE}"
log "  CLOUDWATCH_LOG_GROUP=${CLOUDWATCH_LOG_GROUP}"
log "  COMPOSE_FILE=${COMPOSE_FILE}"
log "══════════════════════════════════════════════════════════════════════"
log ""

# =============================================================================
# Phase 0 — Docker Compose container health check
#
# DEV equivalent of the ECS task health check in hml_integration_test.sh.
# Waits for at least MIN_RUNNING containers to reach "running" state.
# If containers crashloop, shows the last 15 log lines for diagnosis.
# =============================================================================
log "──── Phase 0: Docker Compose container health check  (timeout=${WAIT_DOCKER_SECS}s) ────"
log ""

DEADLINE=$(( $(date +%s) + WAIT_DOCKER_SECS ))
HEALTHY=false

while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  RUNNING=$(docker_running_count)
  CRASHED=$(docker_crashed_list)

  if [ "${RUNNING:-0}" -ge "$MIN_RUNNING" ]; then
    ok "Docker Compose — ${RUNNING} containers RUNNING (mínimo esperado: ${MIN_RUNNING})"
    HEALTHY=true
    break
  fi

  if [ -n "$CRASHED" ]; then
    warn "Containers com problema detectado:"
    for C in $CRASHED; do
      log "   ── logs: ${C} ──"
      docker logs "$C" --tail=15 2>&1 | sed 's/^/      /' || true
      log ""
    done
  fi

  REMAINING=$(( DEADLINE - $(date +%s) ))
  log "   → ${RUNNING}/${MIN_RUNNING} running, aguardando ${POLL_INTERVAL}s (${REMAINING}s restantes) ..."
  sleep "$POLL_INTERVAL"
done

$HEALTHY || fail "Docker Compose — apenas ${RUNNING}/${MIN_RUNNING} containers RUNNING após ${WAIT_DOCKER_SECS}s"
fail_fast "Phase 0 — Docker Compose containers"

# =============================================================================
# Phase 1 — CloudWatch Logs
#
# Verifica se os containers estão emitindo log events no grupo AWS.
# Usa janela de 5 min para capturar containers que subiram logo antes do script.
# =============================================================================
log ""; log "──── Phase 1: CloudWatch Logs  (timeout=${WAIT_LOGS_SECS}s) ────"; log ""

LOOK_START_MS=$(( ($(date +%s) - 300) * 1000 ))
DEADLINE=$(( $(date +%s) + WAIT_LOGS_SECS ))
FOUND=false

while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  EVENTS=$(aws logs filter-log-events \
    --log-group-name "$CLOUDWATCH_LOG_GROUP" \
    --start-time     "$LOOK_START_MS"        \
    --limit          1                        \
    --query          'length(events)'        \
    --output         text --region "$REGION" 2>/dev/null || echo "0")
  if [ "${EVENTS:-0}" -ge 1 ] 2>/dev/null; then
    ok "CW Logs ${CLOUDWATCH_LOG_GROUP} — ${EVENTS} event(s) encontrado(s)"
    FOUND=true
    break
  fi
  log "   → sem eventos ainda, retrying em ${LOG_POLL_INTERVAL}s ..."
  sleep "$LOG_POLL_INTERVAL"
done

if ! $FOUND; then
  warn "Nenhum log event encontrado em ${CLOUDWATCH_LOG_GROUP} após ${WAIT_LOGS_SECS}s"
  warn "Verifique se os containers têm permissão CloudWatch (logs:PutLogEvents) e se CLOUDWATCH_LOG_GROUP está correto no conf/dev.dynamodb.conf"
  fail "CW Logs ${CLOUDWATCH_LOG_GROUP} — nenhum evento após ${WAIT_LOGS_SECS}s"
fi

fail_fast "Phase 1 — CloudWatch Logs"

# =============================================================================
# Phase 2 — SQS
#
# Three-path check:
#   Path 1 (fast): SQS API visible+in-flight (near-realtime)
#   Path 2 (fast): CloudWatch NumberOfMessagesDeleted (near-realtime, ~1 min)
#                  Detecta filas com consumers rápidos onde visible=0 sempre
#   Path 3 (slow): CloudWatch NumberOfMessagesSent (lag ~5 min)
# =============================================================================
log ""; log "──── Phase 2: SQS  (timeout=${WAIT_SQS_SECS}s) ────"; log ""

for QUEUE in "$SQS_QUEUE_MINED_BLOCKS" "$SQS_QUEUE_TXS_HASH_IDS"; do
  log "⏳ SQS ${QUEUE} — polling visible/in-flight + CW Deleted + CW Sent ..."
  DEADLINE=$(( $(date +%s) + WAIT_SQS_SECS ))
  FOUND=false

  SQS_URL=$(aws sqs get-queue-url --queue-name "$QUEUE" --region "$REGION" \
    --query 'QueueUrl' --output text 2>/dev/null || echo "")

  if [ -z "$SQS_URL" ]; then
    fail "SQS ${QUEUE} — fila não encontrada (infra DEV deployada?)"
    continue
  fi

  VISIBLE="0"; INFLIGHT="0"; CW_SENT="None"; CW_DEL="None"
  while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    # Path 1: SQS API attributes (near-realtime)
    VISIBLE=$(aws sqs get-queue-attributes --queue-url "$SQS_URL" \
      --attribute-names ApproximateNumberOfMessages \
      --region "$REGION" \
      --query 'Attributes.ApproximateNumberOfMessages' --output text 2>/dev/null || echo "0")
    INFLIGHT=$(aws sqs get-queue-attributes --queue-url "$SQS_URL" \
      --attribute-names ApproximateNumberOfMessagesNotVisible \
      --region "$REGION" \
      --query 'Attributes.ApproximateNumberOfMessagesNotVisible' --output text 2>/dev/null || echo "0")

    if [ "$(( ${VISIBLE:-0} + ${INFLIGHT:-0} ))" -gt 0 ] 2>/dev/null; then
      ok "SQS ${QUEUE} — tráfego ativo (visible=${VISIBLE}, in-flight=${INFLIGHT})"
      FOUND=true
      break
    fi

    # Path 2: CloudWatch NumberOfMessagesDeleted — janela rolling de 5 min
    # Usa cw_sum (não cw_sum_since) pois a fila tem throughput contínuo:
    # mensagens chegam e são consumidas antes do script iniciar.
    CW_DEL=$(cw_sum "AWS/SQS" "NumberOfMessagesDeleted" "QueueName" "$QUEUE" 300)
    if is_positive "$CW_DEL" 2>/dev/null; then
      ok "SQS ${QUEUE} — NumberOfMessagesDeleted=$(printf '%.0f' "$CW_DEL") nos últimos 5 min (consumers rápidos)"
      FOUND=true
      break
    fi

    # Path 3: CloudWatch NumberOfMessagesSent (~5 min lag)
    CW_SENT=$(cw_sum_since "AWS/SQS" "NumberOfMessagesSent" "QueueName" "$QUEUE" "$SCRIPT_START")
    if is_positive "$CW_SENT" 2>/dev/null; then
      ok "SQS ${QUEUE} — NumberOfMessagesSent=$(printf '%.0f' "$CW_SENT")"
      FOUND=true
      break
    fi

    log "   → sem dados (visible=${VISIBLE}, in-flight=${INFLIGHT}, deleted=${CW_DEL}, sent=${CW_SENT}), retrying em ${POLL_INTERVAL}s ..."
    sleep "$POLL_INTERVAL"
  done

  $FOUND || fail "SQS ${QUEUE} — nenhuma mensagem detectada em ${WAIT_SQS_SECS}s"
done

fail_fast "Phase 2 — SQS"

# =============================================================================
# Phase 3 — Kinesis
#
# Two-path check para lidar com o lag do CloudWatch (~5-10 min):
#   Path 1 (anchored): cw_sum_since SCRIPT_START — sem false-positives de runs anteriores
#   Path 2 (rolling):  cw_sum janela de 10 min — detecta atividade recente quando o lag
#                      CW faz o Path 1 retornar None mesmo havendo dados
#
# Na prática: os containers escrevem no Kinesis continuamente desde que sobem.
# O CW pode levar >7 min para expor esses registros após o script iniciar.
# =============================================================================
log ""; log "──── Phase 3: Kinesis  (timeout=${WAIT_KINESIS_SECS}s — CW lag ~5 min) ────"; log ""

for STREAM in "$KINESIS_STREAM_BLOCKS" "$KINESIS_STREAM_TRANSACTIONS" "$KINESIS_STREAM_DECODED"; do
  log "⏳ Kinesis ${STREAM} — polling CW IncomingRecords (anchored + rolling) ..."

  STREAM_STATUS=$(aws kinesis describe-stream-summary \
    --stream-name "$STREAM" --region "$REGION" \
    --query 'StreamDescriptionSummary.StreamStatus' --output text 2>/dev/null || echo "NOT_FOUND")

  if [ "$STREAM_STATUS" = "NOT_FOUND" ]; then
    fail "Kinesis ${STREAM} — stream não encontrado (infra DEV deployada?)"
    continue
  fi
  log "   → stream encontrado, status=${STREAM_STATUS}"

  DEADLINE=$(( $(date +%s) + WAIT_KINESIS_SECS ))
  FOUND=false

  while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    # Path 1: anchored a SCRIPT_START (sem false-positives de runs anteriores)
    VAL=$(cw_sum_since "AWS/Kinesis" "IncomingRecords" "StreamName" "$STREAM" "$SCRIPT_START")
    if is_positive "$VAL" 2>/dev/null; then
      ok "Kinesis ${STREAM} — IncomingRecords=$(printf '%.0f' "$VAL") (desde script start)"
      FOUND=true
      break
    fi
    # Path 2: rolling 10 min — cobre lag CW > WAIT_KINESIS_SECS quando containers
    # já escreviam antes do script iniciar (caso típico em DEV com containers contínuos)
    VAL2=$(cw_sum "AWS/Kinesis" "IncomingRecords" "StreamName" "$STREAM" 600)
    if is_positive "$VAL2" 2>/dev/null; then
      ok "Kinesis ${STREAM} — IncomingRecords=$(printf '%.0f' "$VAL2") nos últimos 10 min (CW lag)"
      FOUND=true
      break
    fi
    REMAINING=$(( DEADLINE - $(date +%s) ))
    log "   → anchored=${VAL}, rolling-10m=${VAL2}, retrying em ${POLL_INTERVAL}s (${REMAINING}s restantes) ..."
    sleep "$POLL_INTERVAL"
  done

  if ! $FOUND; then
    warn "Kinesis ${STREAM} sem dados — diagnóstico:"
    warn "  1. Verificar se containers escrevem no stream: docker logs python-job-block-data-crawler --tail 10"
    warn "  2. Verificar permissões IAM: kinesis:PutRecord na role do container"
    warn "  3. Verificar nome do stream em conf/dev.dynamodb.conf: KINESIS_STREAM_BLOCKS"
    fail "Kinesis ${STREAM} — nenhum IncomingRecord em ${WAIT_KINESIS_SECS}s"
  fi
done

fail_fast "Phase 3 — Kinesis"

# =============================================================================
# Phase 4 — DynamoDB
# =============================================================================
log ""; log "──── Phase 4: DynamoDB  (timeout=${WAIT_DYNAMODB_SECS}s) ────"; log ""

log "⏳ DynamoDB ${DYNAMODB_TABLE} — polling para items ..."
DEADLINE=$(( $(date +%s) + WAIT_DYNAMODB_SECS ))
FOUND=false

while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  COUNT=$(aws dynamodb scan \
    --region     "$REGION"     \
    --table-name "$DYNAMODB_TABLE" \
    --select     COUNT         \
    --limit      1             \
    --query      'Count'       \
    --output     text 2>/dev/null || echo "0")
  if [ "${COUNT:-0}" -ge 1 ] 2>/dev/null; then
    ok "DynamoDB ${DYNAMODB_TABLE} — Count=${COUNT}"
    FOUND=true
    break
  fi
  log "   → Count=${COUNT}, retrying em ${POLL_INTERVAL}s ..."
  sleep "$POLL_INTERVAL"
done

$FOUND || fail "DynamoDB ${DYNAMODB_TABLE} — 0 items após ${WAIT_DYNAMODB_SECS}s"
fail_fast "Phase 4 — DynamoDB"

# =============================================================================
# Phase 5 — Firehose status
# =============================================================================
log ""; log "──── Phase 5: Firehose  (timeout=${WAIT_PHASE2_SECS}s) ────"; log ""

for FH in \
  "firehose-mainnet-blocks-data-${ENV}" \
  "firehose-mainnet-transactions-data-${ENV}" \
  "firehose-mainnet-transactions-decoded-${ENV}"
do
  log "⏳ Firehose ${FH} — aguardando status ACTIVE ..."
  DEADLINE=$(( $(date +%s) + WAIT_PHASE2_SECS ))
  FH_STATUS="NOT_FOUND"
  FOUND=false

  while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    FH_STATUS=$(aws firehose describe-delivery-stream \
      --region               "$REGION" \
      --delivery-stream-name "$FH"     \
      --query  'DeliveryStreamDescription.DeliveryStreamStatus' \
      --output text 2>/dev/null || echo "NOT_FOUND")
    if [ "$FH_STATUS" = "ACTIVE" ]; then
      ok "Firehose ${FH} — status=ACTIVE"
      FOUND=true
      break
    fi
    log "   → status=${FH_STATUS}, retrying em ${POLL_INTERVAL}s ..."
    sleep "$POLL_INTERVAL"
  done

  $FOUND || fail "Firehose ${FH} — status=${FH_STATUS} após ${WAIT_PHASE2_SECS}s"
done

fail_fast "Phase 5 — Firehose"

# =============================================================================
# Phase 6 — S3 delivery
# Firehose envia dados do Kinesis para S3 (buffer 60s / 1MB).
# Esperado: arquivos .gz em s3://<bucket>/raw/<stream>/year=.../
# =============================================================================
log ""; log "──── Phase 6: S3 Firehose delivery  (timeout=${WAIT_PHASE2_SECS}s) ────"; log ""

for STREAM_PREFIX in \
  "raw/mainnet-blocks-data/" \
  "raw/mainnet-transactions-data/" \
  "raw/mainnet-transactions-decoded/"
do
  log "⏳ S3 s3://${S3_BUCKET}/${STREAM_PREFIX} — aguardando Firehose delivery ..."
  DEADLINE=$(( $(date +%s) + WAIT_PHASE2_SECS ))
  FOUND=false

  while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    NEW_FILE=$(s3_new_gz_file "$S3_BUCKET" "$STREAM_PREFIX" 10 || true)
    if [ -n "$NEW_FILE" ]; then
      ok "S3 ${STREAM_PREFIX} — arquivo entregue: ${NEW_FILE}"
      FOUND=true
      break
    fi
    REMAINING=$(( DEADLINE - $(date +%s) ))
    log "   → sem arquivo novo, retrying em ${POLL_INTERVAL}s (${REMAINING}s restantes) ..."
    sleep "$POLL_INTERVAL"
  done

  $FOUND || fail "S3 ${S3_BUCKET}/${STREAM_PREFIX} — nenhum .gz nos últimos 10 min após ${WAIT_PHASE2_SECS}s"
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
