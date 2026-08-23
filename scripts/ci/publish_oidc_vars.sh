#!/usr/bin/env bash
# publish_oidc_vars.sh — publish the four OIDC deploy-role ARNs as GitHub repository
# variables, read from services/prd/00_bootstrap's Terraform outputs (T-A.4, A2).
#
# The bootstrap stack is operator-applied only (D14, O-1) — this script never applies
# or plans anything; it only reads the ALREADY-APPLIED stack's outputs and republishes
# them as the repository variables every CI workflow's preflight step checks for
# (AWS_DEPLOY_ROLE_DEV, AWS_DEPLOY_ROLE_HML, AWS_DEPLOY_ROLE_PRD, AWS_DEPLOY_ROLE_READONLY).
#
# Default mode is --dry-run: prints the exact `gh variable set` commands without
# executing them. Pass --apply to actually run them (requires `gh auth login` with
# repo-admin scope, and services/prd/00_bootstrap already applied — see
# docs/runbooks/00-bootstrap-apply.md).
#
# Usage:
#   scripts/ci/publish_oidc_vars.sh [--dry-run|--apply] [--repo <owner/repo>]
#
# Required (unless --dry-run with GH_REPO already exported): the repo the variables
# publish to — pass --repo or export GH_REPO.
#
# Terraform output name -> GitHub variable name mapping (the ONE place this mapping is
# declared — nothing else in this repo hardcodes it a second time):
#   gha_deploy_role_dev_arn      -> AWS_DEPLOY_ROLE_DEV
#   gha_deploy_role_hml_arn      -> AWS_DEPLOY_ROLE_HML
#   gha_deploy_role_prd_arn      -> AWS_DEPLOY_ROLE_PRD
#   gha_readonly_role_arn        -> AWS_DEPLOY_ROLE_READONLY
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BOOTSTRAP_DIR="${REPO_ROOT}/services/prd/00_bootstrap"

MODE="--dry-run"
GH_REPO_ARG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) MODE="--dry-run"; shift ;;
    --apply)   MODE="--apply";   shift ;;
    --repo)    GH_REPO_ARG="${2:?--repo requires an owner/repo argument}"; shift 2 ;;
    *) echo "::error::Unknown argument '$1'. Usage: publish_oidc_vars.sh [--dry-run|--apply] [--repo <owner/repo>]" >&2; exit 1 ;;
  esac
done

if ! command -v terraform >/dev/null 2>&1; then
  echo "::error::terraform is required by publish_oidc_vars.sh" >&2
  exit 1
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "::error::jq is required by publish_oidc_vars.sh" >&2
  exit 1
fi
if [[ "${MODE}" == "--apply" ]] && ! command -v gh >/dev/null 2>&1; then
  echo "::error::gh (GitHub CLI) is required for --apply" >&2
  exit 1
fi

echo "==> Reading services/prd/00_bootstrap outputs (never applying/planning it, D14/O-1)..." >&2
OUTPUTS_JSON="$(terraform -chdir="${BOOTSTRAP_DIR}" output -json)"

declare -A TF_TO_GH=(
  [gha_deploy_role_dev_arn]=AWS_DEPLOY_ROLE_DEV
  [gha_deploy_role_hml_arn]=AWS_DEPLOY_ROLE_HML
  [gha_deploy_role_prd_arn]=AWS_DEPLOY_ROLE_PRD
  [gha_readonly_role_arn]=AWS_DEPLOY_ROLE_READONLY
)

GH_REPO_FLAG=()
if [[ -n "${GH_REPO_ARG}" ]]; then
  GH_REPO_FLAG=(--repo "${GH_REPO_ARG}")
fi

MISSING=""
for tf_output in "${!TF_TO_GH[@]}"; do
  value="$(echo "${OUTPUTS_JSON}" | jq -r --arg k "${tf_output}" '.[$k].value // empty')"
  gh_var="${TF_TO_GH[${tf_output}]}"
  if [[ -z "${value}" ]]; then
    MISSING="${MISSING} ${tf_output}"
    continue
  fi
  CMD=(gh variable set "${gh_var}" --body "${value}" "${GH_REPO_FLAG[@]}")
  if [[ "${MODE}" == "--dry-run" ]]; then
    printf '%s\n' "${CMD[*]}"
  else
    echo "==> ${CMD[*]}" >&2
    "${CMD[@]}"
  fi
done

if [[ -n "${MISSING}" ]]; then
  echo "::error::Missing 00_bootstrap output(s):${MISSING}. Is services/prd/00_bootstrap applied? See docs/runbooks/00-bootstrap-apply.md." >&2
  exit 1
fi

if [[ "${MODE}" == "--dry-run" ]]; then
  echo "" >&2
  echo "(dry-run — no variables published. Re-run with --apply to execute.)" >&2
else
  echo "" >&2
  echo "All four AWS_DEPLOY_ROLE_* variables published." >&2
fi
