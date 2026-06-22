#!/usr/bin/env bash
# scripts/prod_resume.sh
#
# Sai do modo standby e restaura o ambiente de produção:
#   1. Retoma clusters interativos do Databricks PROD (via state file)
#
# NOTE (v0.4.0 — capture-layer retirement): the 5 streaming-producer ECS services
# were retired. The ECS rescale block that this script previously carried no longer
# applies — capture now runs in the separate dd-chain-capture project. Only the
# Databricks resume remains.
#
# Pré-requisitos:
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
echo "=== PROD Resume ($(date -u '+%Y-%m-%dT%H:%M:%SZ')) ==="
echo "Region  : $AWS_REGION"
if [ "$DRY_RUN" = "true" ]; then
  echo "Mode    : DRY RUN"
fi
echo ""

# ---------------------------------------------------------------------------
# Databricks: resume interactive clusters
# ---------------------------------------------------------------------------
echo "--- Databricks: resuming interactive clusters ---"

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
echo "  Databricks       → interactive clusters started"
echo ""
