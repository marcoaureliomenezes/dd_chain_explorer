#!/usr/bin/env bash
# scripts/prod_standby.sh
#
# Coloca o ambiente de produção em modo standby:
#   1. Escala todos os ECS services para desired_count=0
#   2. Aguarda o drain de tasks
#   3. Pausa clusters interativos do Databricks PROD
#
# Pré-requisitos:
#   - AWS CLI autenticado (perfil padrão ou AWS_ACCESS_KEY_ID/SECRET em env)
#   - Python + requests instalados (para o script Databricks)
#   - ~/.databrickscfg com perfil [prd] apontando para o workspace URL
#
# Uso:
#   make prod_standby
#   # ou diretamente:
#   bash scripts/prod_standby.sh [--skip-databricks] [--dry-run]
#
set -euo pipefail

AWS_REGION="${AWS_REGION:-sa-east-1}"
ECS_CLUSTER="dm-chain-explorer-ecs"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SKIP_DATABRICKS=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-databricks) SKIP_DATABRICKS=true; shift ;;
    --dry-run)         DRY_RUN=true;         shift ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
ecs_scale() {
  local service="$1"
  local count="$2"
  if [ "$DRY_RUN" = "true" ]; then
    echo "  [DRY RUN] would set $service → desired_count=$count"
    return
  fi
  aws ecs update-service \
    --cluster "$ECS_CLUSTER" \
    --service  "$service" \
    --desired-count "$count" \
    --region   "$AWS_REGION" \
    --query    'service.serviceName' \
    --output   text
}

# ---------------------------------------------------------------------------
# Check AWS connectivity
# ---------------------------------------------------------------------------
echo ""
echo "=== PROD Standby ($(date -u '+%Y-%m-%dT%H:%M:%SZ')) ==="
echo "Cluster : $ECS_CLUSTER"
echo "Region  : $AWS_REGION"
if [ "$DRY_RUN" = "true" ]; then
  echo "Mode    : DRY RUN"
fi
echo ""

if ! aws sts get-caller-identity --region "$AWS_REGION" --query 'Account' --output text &>/dev/null; then
  echo "ERROR: AWS CLI not authenticated. Configure credentials before running standby."
  exit 1
fi

# ---------------------------------------------------------------------------
# Step 1 — ECS: scale all services to 0
# ---------------------------------------------------------------------------
echo "--- [1/3] ECS: scaling services to 0 ---"

declare -A ECS_SERVICES=(
  [dm-mined-blocks-watcher]=1
  [dm-orphan-blocks-watcher]=1
  [dm-block-data-crawler]=1
  [dm-mined-txs-crawler]=8
  [dm-txs-input-decoder]=3
)

for SERVICE in "${!ECS_SERVICES[@]}"; do
  echo -n "  Scaling $SERVICE → 0 ... "
  ecs_scale "$SERVICE" 0
  echo "[OK]"
done

# ---------------------------------------------------------------------------
# Step 2 — ECS: wait for all tasks to drain
# ---------------------------------------------------------------------------
if [ "$DRY_RUN" = "false" ]; then
  echo ""
  echo "--- [2/3] ECS: waiting for tasks to drain (timeout: 5 min) ---"
  SERVICES_LIST=$(echo "${!ECS_SERVICES[@]}" | tr ' ' '\n' | sort | tr '\n' ' ')
  aws ecs wait services-stable \
    --cluster "$ECS_CLUSTER" \
    --services $SERVICES_LIST \
    --region  "$AWS_REGION" \
    2>/dev/null && echo "  All ECS tasks drained." \
    || echo "  [WARN] Timed out waiting for drain — tasks may still be stopping."
else
  echo ""
  echo "--- [2/3] ECS: wait (skipped in dry-run) ---"
fi

# ---------------------------------------------------------------------------
# Step 3 — Databricks: pause interactive clusters
# ---------------------------------------------------------------------------
echo ""
echo "--- [3/3] Databricks: pausing interactive clusters ---"

if [ "$SKIP_DATABRICKS" = "true" ]; then
  echo "  Skipped (--skip-databricks)."
elif ! command -v python3 &>/dev/null; then
  echo "  [WARN] python3 not found — skipping Databricks pause."
  echo "         Run manually: python3 scripts/pause_databricks_clusters.py"
else
  PAUSE_FLAGS=""
  [ "$DRY_RUN" = "true" ] && PAUSE_FLAGS="--dry-run"
  python3 "$SCRIPT_DIR/pause_databricks_clusters.py" $PAUSE_FLAGS || {
    echo "  [WARN] Databricks pause failed. Check ~/.databrickscfg [prd] profile."
    echo "         ECS services are already scaled to 0."
  }
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "=== Standby complete ==="
echo ""
echo "Resources standing by:"
echo "  ECS services (${#ECS_SERVICES[@]}) → desired_count=0 (no Fargate charges)"
echo "  Databricks interactive clusters    → terminated (no DBU charges)"
echo ""
echo "To resume: make prod_resume"
echo ""
