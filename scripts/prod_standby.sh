#!/usr/bin/env bash
# scripts/prod_standby.sh
#
# Coloca o ambiente de produção em modo standby:
#   1. Pausa clusters interativos do Databricks PROD
#
# NOTE (v0.4.0 — capture-layer retirement): the 5 streaming-producer ECS services
# were retired (capture now runs in the separate dd-chain-capture project), so the
# ECS scale-to-0 block this script previously carried no longer applies. Only the
# Databricks pause remains.
#
# Pré-requisitos:
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
# Banner
# ---------------------------------------------------------------------------
echo ""
echo "=== PROD Standby ($(date -u '+%Y-%m-%dT%H:%M:%SZ')) ==="
echo "Region  : $AWS_REGION"
if [ "$DRY_RUN" = "true" ]; then
  echo "Mode    : DRY RUN"
fi
echo ""

# ---------------------------------------------------------------------------
# Databricks: pause interactive clusters
# ---------------------------------------------------------------------------
echo "--- Databricks: pausing interactive clusters ---"

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
echo "  Databricks interactive clusters    → terminated (no DBU charges)"
echo ""
echo "To resume: make prod_resume"
echo ""
