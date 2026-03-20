#!/usr/bin/env bash
# scripts/prod_resume.sh
#
# Sai do modo standby e restaura o ambiente de produção:
#   1. Restaura ECS services para os desired_counts de produção
#   2. Aguarda os services estabilizarem
#   3. Retoma clusters interativos do Databricks PROD (via state file)
#
# Desired counts de produção (hardcoded — valores estáveis):
#   dm-mined-blocks-watcher  → 1
#   dm-orphan-blocks-watcher → 1
#   dm-block-data-crawler    → 1
#   dm-mined-txs-crawler     → 8
#   dm-txs-input-decoder     → 3
#
# Pré-requisitos:
#   - AWS CLI autenticado
#   - Python + requests instalados
#   - ~/.databrickscfg com perfil [prd] apontando para o workspace URL
#
# Uso:
#   make prod_resume
#   # ou diretamente:
#   bash scripts/prod_resume.sh [--skip-databricks] [--dry-run]
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
# Production desired_count map
# ---------------------------------------------------------------------------
declare -A ECS_PROD_COUNTS=(
  [dm-mined-blocks-watcher]=1
  [dm-orphan-blocks-watcher]=1
  [dm-block-data-crawler]=1
  [dm-mined-txs-crawler]=8
  [dm-txs-input-decoder]=3
)

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
echo "=== PROD Resume ($(date -u '+%Y-%m-%dT%H:%M:%SZ')) ==="
echo "Cluster : $ECS_CLUSTER"
echo "Region  : $AWS_REGION"
if [ "$DRY_RUN" = "true" ]; then
  echo "Mode    : DRY RUN"
fi
echo ""

if ! aws sts get-caller-identity --region "$AWS_REGION" --query 'Account' --output text &>/dev/null; then
  echo "ERROR: AWS CLI not authenticated. Configure credentials before running resume."
  exit 1
fi

# ---------------------------------------------------------------------------
# Step 1 — ECS: restore production desired_counts
# ---------------------------------------------------------------------------
echo "--- [1/3] ECS: restoring production desired_counts ---"

for SERVICE in "${!ECS_PROD_COUNTS[@]}"; do
  COUNT="${ECS_PROD_COUNTS[$SERVICE]}"
  echo -n "  Scaling $SERVICE → $COUNT ... "
  ecs_scale "$SERVICE" "$COUNT"
  echo "[OK]"
done

# ---------------------------------------------------------------------------
# Step 2 — ECS: wait for all services to stabilize
# ---------------------------------------------------------------------------
if [ "$DRY_RUN" = "false" ]; then
  echo ""
  echo "--- [2/3] ECS: waiting for services to stabilize (timeout: 10 min) ---"
  echo "  Waiting..."

  SERVICES_LIST=$(echo "${!ECS_PROD_COUNTS[@]}" | tr ' ' '\n' | sort | tr '\n' ' ')
  aws ecs wait services-stable \
    --cluster "$ECS_CLUSTER" \
    --services $SERVICES_LIST \
    --region  "$AWS_REGION" \
    2>/dev/null && echo "  All ECS services are stable." \
    || echo "  [WARN] Timed out waiting for stability — check CloudWatch: /ecs/dm-chain-explorer"
else
  echo ""
  echo "--- [2/3] ECS: wait (skipped in dry-run) ---"
fi

# ---------------------------------------------------------------------------
# Step 3 — Databricks: resume interactive clusters
# ---------------------------------------------------------------------------
echo ""
echo "--- [3/3] Databricks: resuming interactive clusters ---"

if [ "$SKIP_DATABRICKS" = "true" ]; then
  echo "  Skipped (--skip-databricks)."
elif ! command -v python3 &>/dev/null; then
  echo "  [WARN] python3 not found — skipping Databricks resume."
  echo "         Run manually: python3 scripts/resume_databricks_clusters.py"
else
  RESUME_FLAGS=""
  [ "$DRY_RUN" = "true" ] && RESUME_FLAGS="--dry-run"
  python3 "$SCRIPT_DIR/resume_databricks_clusters.py" $RESUME_FLAGS || {
    echo "  [WARN] Databricks resume failed or no state file found."
    echo "         Start clusters manually from the Databricks UI if needed."
  }
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "=== Resume complete ==="
echo ""
echo "Production resources restored:"
TOTAL_TASKS=0
for COUNT in "${ECS_PROD_COUNTS[@]}"; do TOTAL_TASKS=$((TOTAL_TASKS + COUNT)); done
echo "  ECS tasks        → $TOTAL_TASKS tasks running across ${#ECS_PROD_COUNTS[@]} services"
echo "  Databricks       → interactive clusters started"
echo ""
echo "Monitor at:"
echo "  ECS    → https://console.aws.amazon.com/ecs/home?region=${AWS_REGION}#/clusters/${ECS_CLUSTER}/services"
echo "  Logs   → aws logs tail /ecs/dm-chain-explorer --follow"
echo ""
