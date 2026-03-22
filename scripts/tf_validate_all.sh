#!/usr/bin/env bash
# tf_validate_all.sh — Validate + optionally plan all Terraform modules locally.
#
# Usage:
#   ./scripts/tf_validate_all.sh [--plan] [--module <path>]
#
# Flags:
#   --plan      Run terraform plan (requires AWS credentials + initialized backends)
#   --module    Validate only the specified module path (relative to repo root)
#
# Exit codes:
#   0  All modules passed
#   1  One or more modules failed

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN_PLAN=false
FILTER_MODULE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --plan)     RUN_PLAN=true; shift ;;
    --module)   FILTER_MODULE="$2"; shift 2 ;;
    *)          echo "Unknown flag: $1"; exit 1 ;;
  esac
done

MODULES=(
  services/dev/01_peripherals
  services/dev/02_lambda
  services/prd/02_vpc
  services/prd/03_iam
  services/prd/04_peripherals
  services/prd/05_databricks
  services/prd/06_lambda
  services/prd/07_ecs
)

PASS=()
FAIL=()
SKIP=()

GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[0;33m"
NC="\033[0m"

run_module() {
  local MODULE="$1"
  local DIR="$REPO_ROOT/$MODULE"

  if [ ! -d "$DIR" ]; then
    echo -e "  ${YELLOW}[SKIP]${NC} Directory not found: $MODULE"
    SKIP+=("$MODULE")
    return
  fi

  echo ""
  echo -e "${YELLOW}▶ $MODULE${NC}"

  # init -backend=false (no AWS creds needed, installs providers)
  if ! terraform -chdir="$DIR" init -backend=false -upgrade -no-color -input=false > /tmp/tf_init.log 2>&1; then
    echo -e "  ${RED}[FAIL]${NC} init -backend=false"
    cat /tmp/tf_init.log | tail -5
    FAIL+=("$MODULE (init)")
    return
  fi
  echo -e "  ${GREEN}[OK]${NC}   init -backend=false"

  # validate
  if ! terraform -chdir="$DIR" validate -no-color > /tmp/tf_validate.log 2>&1; then
    echo -e "  ${RED}[FAIL]${NC} validate"
    cat /tmp/tf_validate.log
    FAIL+=("$MODULE (validate)")
    return
  fi
  echo -e "  ${GREEN}[OK]${NC}   validate"

  # plan (optional — requires real backend + credentials)
  if [ "$RUN_PLAN" = true ]; then
    # Re-init with real backend
    if ! terraform -chdir="$DIR" init -reconfigure -no-color -input=false > /tmp/tf_init_be.log 2>&1; then
      echo -e "  ${YELLOW}[SKIP]${NC} plan — backend init failed (no creds?)"
      cat /tmp/tf_init_be.log | tail -3
      SKIP+=("$MODULE (plan-init)")
      return
    fi
    if ! terraform -chdir="$DIR" plan -no-color -input=false -detailed-exitcode > /tmp/tf_plan.log 2>&1; then
      EXIT=$?
      if [ $EXIT -eq 2 ]; then
        echo -e "  ${YELLOW}[DIFF]${NC} plan — changes detected (not an error)"
        PASS+=("$MODULE")
      else
        echo -e "  ${RED}[FAIL]${NC} plan"
        grep -E "^│ Error|^Error" /tmp/tf_plan.log | head -10
        FAIL+=("$MODULE (plan)")
        return
      fi
    else
      echo -e "  ${GREEN}[OK]${NC}   plan — no changes"
      PASS+=("$MODULE")
    fi
  else
    PASS+=("$MODULE")
  fi
}

echo "============================================"
echo " Terraform Validation — $(date '+%Y-%m-%d %H:%M:%S')"
echo " Mode: $([ "$RUN_PLAN" = true ] && echo 'validate + plan' || echo 'validate only')"
echo "============================================"

for MODULE in "${MODULES[@]}"; do
  if [ -n "$FILTER_MODULE" ] && [ "$MODULE" != "$FILTER_MODULE" ]; then
    continue
  fi
  run_module "$MODULE"
done

echo ""
echo "============================================"
echo " Results"
echo "============================================"
echo -e " ${GREEN}PASS${NC}: ${#PASS[@]} — ${PASS[*]:-none}"
echo -e " ${YELLOW}SKIP${NC}: ${#SKIP[@]} — ${SKIP[*]:-none}"
echo -e " ${RED}FAIL${NC}: ${#FAIL[@]} — ${FAIL[*]:-none}"
echo "============================================"

if [ ${#FAIL[@]} -gt 0 ]; then
  exit 1
fi
exit 0
