#!/usr/bin/env bash
# stack_list.sh — single-source stack-id enumeration (T-A.8, F-ARCH-4).
#
# Emits, one per line, the stack ids scripts/ci/stack_map.json declares for a given
# environment, in the map's declared order — excluding operator_only stacks always
# (CI must never plan/apply/destroy them, D14/O-1), and additionally excluding
# never_destroy stacks when --destroyable is given (CI must never destroy them, even
# though it may plan/apply them normally).
#
# No caller (plan_on_pr.yml, drift_detection.yml, destroy_all_cloud_infra.yml,
# deploy_env.sh, destroy_env.sh, plan_env.sh, ...) hardcodes a stack id list — every
# one resolves membership through this helper (or, for the per-stack field lookups
# deploy_env.sh already had, directly through the map it reads via this same file).
#
# Usage:
#   scripts/ci/stack_list.sh <env> [--destroyable]
#
# Arguments:
#   env           — dev | hml | prd
#   --destroyable — also exclude never_destroy stacks (for a destroy-path caller)
#
# Optional env vars:
#   STACK_MAP — path to the stack map JSON (default: scripts/ci/stack_map.json,
#               resolved relative to this script's own directory).
set -euo pipefail

ENV="${1:-}"
MODE="${2:-}"

if [[ -z "$ENV" ]]; then
  echo "Usage: stack_list.sh <env> [--destroyable]" >&2
  exit 1
fi

CI_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_MAP="${STACK_MAP:-${CI_DIR}/stack_map.json}"

if ! command -v jq >/dev/null 2>&1; then
  echo "::error::jq is required by stack_list.sh" >&2
  exit 1
fi
if [[ ! -f "$STACK_MAP" ]]; then
  echo "::error::stack map not found: ${STACK_MAP}" >&2
  exit 1
fi

FILTER='(.operator_only // false) == false'
if [[ "$MODE" == "--destroyable" ]]; then
  FILTER="${FILTER} and ((.never_destroy // false) == false)"
elif [[ -n "$MODE" ]]; then
  echo "::error::Unknown stack_list.sh mode '${MODE}' (expected --destroyable or nothing)" >&2
  exit 1
fi

if ! jq -e --arg e "$ENV" 'has("environments") and (.environments | has($e))' "$STACK_MAP" >/dev/null; then
  echo "::error::stack_list.sh: unknown environment '${ENV}' in ${STACK_MAP}" >&2
  exit 1
fi

jq -r --arg e "$ENV" ".environments[\$e].stacks[] | select(${FILTER}) | .id" "$STACK_MAP"
