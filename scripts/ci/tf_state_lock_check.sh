#!/usr/bin/env bash
# tf_state_lock_check.sh — Verifica e remove locks órfãos do Terraform state.
#
# Um lock é considerado órfão se tiver mais de MAX_LOCK_AGE_MINUTES minutos de idade,
# indicando que o run anterior falhou e não liberou o lock corretamente.
#
# Uso:
#   bash scripts/ci/tf_state_lock_check.sh [--dry-run]
#
# Env vars opcionais:
#   MAX_LOCK_AGE_MINUTES   — idade mínima para remover lock (default: 60)
#   LOCK_TABLE             — nome da tabela DynamoDB (default: dm-chain-explorer-terraform-lock)
#   AWS_REGION             — região AWS (default: sa-east-1)
set -euo pipefail

MAX_LOCK_AGE_MINUTES="${MAX_LOCK_AGE_MINUTES:-60}"
LOCK_TABLE="${LOCK_TABLE:-dm-chain-explorer-terraform-lock}"
AWS_REGION="${AWS_REGION:-sa-east-1}"
DRY_RUN=false

for arg in "$@"; do
  [ "$arg" = "--dry-run" ] && DRY_RUN=true
done

echo "==> Checking Terraform state locks (table=${LOCK_TABLE}, max_age=${MAX_LOCK_AGE_MINUTES}min)"

# Listar todos os locks ativos
LOCKS=$(aws dynamodb scan \
  --table-name "$LOCK_TABLE" \
  --region "$AWS_REGION" \
  --query 'Items[*]' \
  --output json 2>/dev/null || echo "[]")

LOCK_COUNT=$(echo "$LOCKS" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

if [ "${LOCK_COUNT:-0}" -eq 0 ]; then
  echo "  ✅ No active state locks found."
  exit 0
fi

echo "  Found ${LOCK_COUNT} lock(s). Checking ages..."

NOW_EPOCH=$(date +%s)
REMOVED=0
SKIPPED=0

echo "$LOCKS" | python3 -c "
import sys, json, datetime

locks = json.load(sys.stdin)
now_epoch = $NOW_EPOCH
max_age_secs = $MAX_LOCK_AGE_MINUTES * 60

for item in locks:
    lock_id = item.get('LockID', {}).get('S', '')
    info_raw = item.get('Info', {}).get('S', '{}')
    try:
        info = json.loads(info_raw)
    except Exception:
        info = {}
    created_str = info.get('Created', '')
    path = info.get('Path', lock_id)
    operation = info.get('Operation', '?')
    who = info.get('Who', '?')

    age_secs = None
    if created_str:
        try:
            created_dt = datetime.datetime.fromisoformat(created_str.replace('Z', '+00:00'))
            age_secs = now_epoch - int(created_dt.timestamp())
        except Exception:
            pass

    age_str = f'{age_secs//60}min' if age_secs is not None else 'unknown'
    stale = (age_secs is not None and age_secs > max_age_secs) or age_secs is None

    print(f'LOCK|{lock_id}|{path}|{operation}|{who}|{age_str}|{\"STALE\" if stale else \"ACTIVE\"}')
" | while IFS='|' read -r _ lock_id path operation who age_str staleness; do
    echo "    Lock: ${path}"
    echo "          operation=${operation} | who=${who} | age=${age_str} | status=${staleness}"

    if [ "$staleness" = "STALE" ]; then
      if $DRY_RUN; then
        echo "          [DRY-RUN] Would remove lock: LockID=${lock_id}"
        SKIPPED=$((SKIPPED + 1))
      else
        echo "          ⚠️  Removing stale lock..."
        aws dynamodb delete-item \
          --table-name "$LOCK_TABLE" \
          --region "$AWS_REGION" \
          --key "{\"LockID\": {\"S\": \"${lock_id}\"}}" 2>/dev/null \
          && echo "          ✅ Lock removed." \
          || echo "          ❌ Failed to remove lock (already gone?)."
        REMOVED=$((REMOVED + 1))
      fi
    else
      echo "          ✅ Lock is recent — NOT removing (possible active run)."
    fi
  done

echo ""
if $DRY_RUN; then
  echo "  [DRY-RUN] Summary: ${LOCK_COUNT} lock(s) found, no action taken."
else
  echo "  Summary: ${LOCK_COUNT} lock(s) checked, stale locks removed."
fi
