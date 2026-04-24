#!/usr/bin/env bash
# deploy_all.sh — Deploy DABs components in apps/dabs/ with version-aware skip logic.
#
# Each subdirectory with a databricks.yml is an autonomous DABs component.
# A component is SKIPPED when the PRD git tag dabs/{bundle-name}-v{VERSION} already exists.
# VERSION is read from the VERSION file inside each component directory.
#
# Usage:
#   ./deploy_all.sh dev                              # Deploy all to dev
#   ./deploy_all.sh hml                              # Deploy all to hml (skips PRD-tagged)
#   ./deploy_all.sh prod --tag                       # Deploy to prod, then create git tags
#   ./deploy_all.sh dev dlt_ethereum job_ddl_setup   # Deploy specific components
#
# Exit codes:
#   0 = all deployments (if any) succeeded
#   1 = missing VERSION file or at least one deploy failed
#
# Environment variables (for CI/CD):
#   DATABRICKS_HOST   — Databricks workspace URL
#   DATABRICKS_TOKEN  — PAT token (DEV/HML) or set via OAuth (PROD)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Parse arguments ──────────────────────────────────────────────────────────
TARGET="${1:-dev}"
shift || true

DO_TAG=false
FILTER_COMPONENTS=()
for arg in "$@"; do
  if [[ "$arg" == "--tag" ]]; then
    DO_TAG=true
  else
    FILTER_COMPONENTS+=("$arg")
  fi
done

# ── Colors ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BOLD}${CYAN}DABs Deploy — target: ${TARGET}${NC}"
[[ "$DO_TAG" == true ]] && echo -e "${BOLD}  (will create git tags after successful PRD deploys)${NC}"
echo ""

# Fetch remote tags so we can check what's already deployed in PRD
echo "Fetching remote tags..."
git fetch --tags --quiet 2>/dev/null || echo -e "${YELLOW}Warning: could not fetch remote tags (offline?)${NC}"
echo ""

DEPLOYED=()
SKIPPED=()
FAILED=()

for component_dir in "${SCRIPT_DIR}"/*/; do
  component_name="$(basename "${component_dir}")"

  # Skip hidden dirs, _DEPRECATED etc., and any dir without databricks.yml
  [[ "$component_name" == _* ]] && continue
  [[ "$component_name" == .* ]] && continue
  [[ ! -f "${component_dir}databricks.yml" ]] && continue

  # Optional component filter
  if [[ ${#FILTER_COMPONENTS[@]} -gt 0 ]]; then
    match=0
    for f in "${FILTER_COMPONENTS[@]}"; do
      [[ "$component_name" == "$f" ]] && match=1 && break
    done
    [[ $match -eq 0 ]] && continue
  fi

  # ── Read VERSION (hard fail if missing) ────────────────────────────────
  VERSION_FILE="${component_dir}VERSION"
  if [[ ! -f "$VERSION_FILE" ]]; then
    echo -e "${RED}ERROR: Missing VERSION file in ${component_name}${NC}"
    FAILED+=("$component_name (missing VERSION)")
    continue
  fi
  VERSION=$(tr -d '[:space:]' < "$VERSION_FILE")

  # ── Get bundle name → build PRD tag ────────────────────────────────────
  BUNDLE_NAME=$(grep -m1 "^  name:" "${component_dir}databricks.yml" | awk '{print $2}')
  PRD_TAG="dabs/${BUNDLE_NAME}-v${VERSION}"

  # ── Skip if PRD tag already exists ─────────────────────────────────────
  if git tag -l "$PRD_TAG" | grep -q "$PRD_TAG"; then
    echo -e "  ${YELLOW}[SKIP]${NC}   ${component_name} @ ${VERSION} — tag ${PRD_TAG} exists"
    SKIPPED+=("$component_name")
    continue
  fi

  # ── Deploy ─────────────────────────────────────────────────────────────
  echo -e "  ${CYAN}[DEPLOY]${NC}  ${component_name} @ ${VERSION} → target=${TARGET}"
  if (cd "${component_dir}" && databricks bundle deploy --target "${TARGET}"); then
    echo -e "  ${GREEN}[OK]${NC}     ${component_name}"
    DEPLOYED+=("${component_name}:${PRD_TAG}")
  else
    echo -e "  ${RED}[FAIL]${NC}   ${component_name}"
    FAILED+=("$component_name")
  fi
  echo ""
done

# ── Summary ─────────────────────────────────────────────────────────────────
echo "══════════════════════════════════════════════════"
echo -e "Deployed: ${GREEN}${#DEPLOYED[@]}${NC}  |  Skipped: ${YELLOW}${#SKIPPED[@]}${NC}  |  Failed: ${RED}${#FAILED[@]}${NC}"

if [[ ${#DEPLOYED[@]} -gt 0 ]]; then
  echo ""
  echo "Deployed components:"
  for entry in "${DEPLOYED[@]}"; do
    echo -e "  ${GREEN}✔${NC}  ${entry%%:*}"
  done
fi

if [[ ${#SKIPPED[@]} -gt 0 ]]; then
  echo ""
  echo "Skipped (already in PRD):"
  for s in "${SKIPPED[@]}"; do
    echo -e "  ${YELLOW}–${NC}  $s"
  done
fi

# ── Fail fast if any missing VERSION or deploy failures ──────────────────────
if [[ ${#FAILED[@]} -gt 0 ]]; then
  echo ""
  echo -e "${RED}FAILED:${NC}"
  for f in "${FAILED[@]}"; do
    echo -e "  ${RED}✘${NC}  $f"
  done
  exit 1
fi

# ── Create PRD git tags for each successfully deployed component ─────────────
if [[ "$DO_TAG" == true && ${#DEPLOYED[@]} -gt 0 ]]; then
  echo ""
  echo "Creating git tags for deployed components..."
  for entry in "${DEPLOYED[@]}"; do
    TAG="${entry##*:}"
    COMP="${entry%%:*}"
    if git tag -a "$TAG" -m "DABs deploy: ${COMP} ${TAG}"; then
      echo -e "  ${GREEN}Tagged${NC}: $TAG"
    else
      echo -e "  ${YELLOW}Tag already exists (skipped)${NC}: $TAG"
    fi
  done
  echo "Pushing tags to origin..."
  git push origin --tags --quiet
  echo -e "${GREEN}Tags pushed.${NC}"
fi

echo ""
echo -e "${GREEN}Done.${NC}"
exit 0
