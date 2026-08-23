#!/usr/bin/env bash
# destroy_env.sh — Sequential, map-driven destroy of every destroyable Terraform stack
# for a given environment (T-A.8, F-ARCH-4).
#
# The stack list and destroy order are NOT hardcoded here — they are read from the
# single-source map scripts/ci/stack_map.json via scripts/ci/stack_list.sh <env>
# --destroyable (excludes operator_only stacks always, e.g. prd/00_bootstrap, D14/O-1;
# and never_destroy stacks, e.g. prd/01_tf_state — the remote-state backend every other
# stack's apply/destroy depends on), applied in REVERSE declared order (downstream
# stacks first) so a stack is never destroyed while a dependent still references it.
#
# S3 buckets in the environment are emptied first (all object versions) since a
# non-empty bucket blocks `terraform destroy`. Idempotent: a resource absent from TF
# state is a no-op.
#
# set -e: if a stack destroy fails, downstream (in destroy order — i.e. upstream in the
# dependency graph) stacks are NOT destroyed, preventing orphaned resources whose
# dependencies are already gone.
#
# Usage:
#   bash scripts/ci/destroy_env.sh <environment>
#
# Arguments:
#   environment — dev | hml | prd
#
# AWS credentials must already be configured on the runner (or locally, operator-gated).
set -euo pipefail

ENV="${1:-}"

if [[ -z "$ENV" ]]; then
  echo "::error::Usage: destroy_env.sh <dev|hml|prd>"
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STACK_MAP="${STACK_MAP:-${REPO_ROOT}/scripts/ci/stack_map.json}"

if ! command -v jq >/dev/null 2>&1; then
  echo "::error::jq is required by destroy_env.sh"
  exit 1
fi

# ── Helpers ───────────────────────────────────────────────────────────────────

summary() { echo "$*" >> "${GITHUB_STEP_SUMMARY:-/dev/null}"; }

stack_field() {
  local sid="$1" field="$2"
  jq -r --arg e "$ENV" --arg s "$sid" --arg f "$field" \
    '.environments[$e].stacks[] | select(.id==$s) | .[$f]' "$STACK_MAP"
}

destroy_module() {
  local module_dir="$1"   # absolute path to module directory
  local module_name="$2"  # display name for summary

  echo ""
  echo "════════════════════════════════════════════════════════"
  echo "  DESTROYING: ${module_name}"
  echo "  DIR:  ${module_dir}"
  echo "════════════════════════════════════════════════════════"

  cd "${module_dir}"

  # State lock check — fail loud on a real lock (parity with deploy_env.sh, F-QA-A1-4).
  # A held lock must NOT be swallowed: destroying over another writer's lock races it and
  # can corrupt remote state. tf_state_lock_check.sh already only removes STALE locks and
  # is a no-op when none exist, so failing here means a genuine active lock.
  if ! bash "${REPO_ROOT}/scripts/ci/tf_state_lock_check.sh"; then
    summary "| ❌ | ${module_name} | state lock check failed |"
    echo "::error::State lock check failed for ${module_name}"
    exit 1
  fi

  terraform init -input=false

  terraform destroy -auto-approve -input=false -no-color

  summary "| ✅ | ${module_name} | destroyed |"
  cd "${REPO_ROOT}"
}

# ── Entry point ───────────────────────────────────────────────────────────────

summary ""
summary "## Destroy \`${ENV}\` — $(date -u '+%Y-%m-%d %H:%M UTC')"
summary ""
summary "| Status | Module | Result |"
summary "|--------|--------|--------|"

case "$ENV" in
  dev|hml|prd) ;;
  *)
    echo "::error::Unknown environment '${ENV}'. Supported: dev, hml, prd"
    exit 1
    ;;
esac

echo "==> Emptying ${ENV} S3 buckets (all object versions) before destroy..."
bash "${REPO_ROOT}/scripts/ci/empty_s3_and_ecr.sh" "${ENV}" || \
  echo "::warning::empty_s3_and_ecr.sh ${ENV} reported a non-zero exit — continuing (idempotent, may be a no-op environment)."

# Destroy in REVERSE declared order (downstream stacks first) — mirrors
# deploy_env.sh's forward, upstream-first apply order.
mapfile -t STACK_IDS < <(bash "${REPO_ROOT}/scripts/ci/stack_list.sh" "${ENV}" --destroyable)
if [[ "${#STACK_IDS[@]}" -eq 0 ]]; then
  echo "::error::No destroyable stacks declared for environment '${ENV}' in ${STACK_MAP}"
  exit 1
fi

for (( idx=${#STACK_IDS[@]}-1 ; idx>=0 ; idx-- )); do
  sid="${STACK_IDS[$idx]}"
  label="$(stack_field "$sid" label)"
  path="$(stack_field "$sid" path)"
  destroy_module "${REPO_ROOT}/${path}" "${label}"
done

summary ""
summary "> ${ENV} destroy complete."

echo ""
echo "✅ destroy_env.sh ${ENV} — DONE"
