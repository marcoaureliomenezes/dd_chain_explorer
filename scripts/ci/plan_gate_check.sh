#!/usr/bin/env bash
# plan_gate_check.sh — informed-gate safety checks over Terraform plan text output.
#
# Two subcommands, both pure functions of plan.txt files (no terraform/AWS calls), so
# they are unit-testable against fixture plans (T-R6-A2(c), F-QA-2):
#
#   destroy-ack <ack> <plan.txt> [plan.txt ...]
#     Destroy acknowledgment gate (ADR-R6-4). Scans every given plan for pending
#     destroys (the `Plan: A to add, C to change, D to destroy.` footer with D>0, or a
#     `# <addr> will be destroyed` line). If ANY plan destroys and <ack> is not a
#     truthy acknowledgment (true|yes|1), exit 2 (loud refusal). With ack, or with no
#     destroys anywhere, exit 0.
#       <ack> truthy values: true | yes | 1  (case-insensitive). Anything else = not ack.
#
#   counts <plan.txt>
#     Print the "add change destroy" triple parsed from a plan.txt (or "0 0 0").
#     Single source of plan-count parsing for the plan-phase summary.
#
#   plan-diff <approved.txt> <replan.txt>
#     Cross-stack divergence gate (ADR-R6-5). Compares the approved pre-gate plan
#     against a post-upstream-apply re-plan for the same stack. Compares the
#     add/change/destroy counts AND the set of changed resource addresses. Exit 0 if
#     they match (apply may proceed against the re-planned tfplan); exit 3 if they
#     diverge (the caller FAILS CLOSED — no further downstream applies — and publishes
#     this diff as artifact + job summary, per the ADR-R6-5 pinned mechanism). A
#     missing approved plan (no pre-gate plan for a downstream stack) is also a
#     divergence -> exit 3.
#
# Exit codes:
#   0  ok (no destroys / acknowledged / re-plan matches approved)
#   2  destroy without acknowledgment
#   3  re-plan diverges from approved plan (or approved plan missing)
#   64 usage error
set -euo pipefail

err() { echo "::error::$*" >&2; }

# Print the "A C D" add/change/destroy triple parsed from a plan.txt, or "0 0 0".
plan_counts() {
  local plan_file="$1"
  if [[ ! -f "$plan_file" ]]; then
    echo "0 0 0"
    return 0
  fi
  # Last matching footer wins (terraform prints it once near the end).
  local line
  line="$(grep -E '^Plan: [0-9]+ to add, [0-9]+ to change, [0-9]+ to destroy\.' "$plan_file" | tail -1 || true)"
  if [[ -z "$line" ]]; then
    # "No changes." plans, or apply-time plans with nothing pending.
    echo "0 0 0"
    return 0
  fi
  local add change destroy
  add="$(sed -E 's/^Plan: ([0-9]+) to add.*/\1/' <<<"$line")"
  change="$(sed -E 's/.* ([0-9]+) to change.*/\1/' <<<"$line")"
  destroy="$(sed -E 's/.* ([0-9]+) to destroy\..*/\1/' <<<"$line")"
  echo "${add} ${change} ${destroy}"
}

# Print the sorted set of resource addresses with a pending action, one per line.
# Terraform marks each with a `# <address> will be <action>` comment line.
plan_addresses() {
  local plan_file="$1"
  [[ -f "$plan_file" ]] || return 0
  grep -E '^[[:space:]]*# .* will be (created|destroyed|updated in-place|replaced|read during apply)' "$plan_file" \
    | sed -E 's/^[[:space:]]*# (.*) will be .*/\1/' \
    | sort -u
}

# Return 0 (true) if the plan has any pending destroy.
plan_has_destroy() {
  local plan_file="$1"
  read -r _a _c destroy < <(plan_counts "$plan_file")
  if [[ "${destroy:-0}" -gt 0 ]]; then
    return 0
  fi
  # Defensive: also catch an explicit "will be destroyed" address even if the footer
  # is absent/garbled.
  if [[ -f "$plan_file" ]] && grep -qE '^[[:space:]]*# .* will be destroyed' "$plan_file"; then
    return 0
  fi
  return 1
}

is_ack() {
  case "$(tr '[:upper:]' '[:lower:]' <<<"${1:-}")" in
    true|yes|1) return 0 ;;
    *) return 1 ;;
  esac
}

cmd_destroy_ack() {
  if [[ "$#" -lt 2 ]]; then
    err "usage: plan_gate_check.sh destroy-ack <ack> <plan.txt> [plan.txt ...]"
    exit 64
  fi
  local ack="$1"; shift
  local destroying=()
  local f
  for f in "$@"; do
    if plan_has_destroy "$f"; then
      destroying+=("$f")
    fi
  done

  if [[ "${#destroying[@]}" -eq 0 ]]; then
    echo "plan-gate: no destroys detected across ${#} plan(s); gate OK."
    return 0
  fi

  if is_ack "$ack"; then
    echo "plan-gate: destroys detected in ${#destroying[@]} plan(s); acknowledged — gate OK."
    printf '  - %s\n' "${destroying[@]}"
    return 0
  fi

  err "Plan(s) contain resource DESTROYS but the destroy acknowledgment input was not set."
  echo "Stacks with destroys:" >&2
  printf '  - %s\n' "${destroying[@]}" >&2
  echo "Re-run the deploy with the destroy-acknowledgment input enabled to proceed." >&2
  exit 2
}

cmd_plan_diff() {
  if [[ "$#" -ne 2 ]]; then
    err "usage: plan_gate_check.sh plan-diff <approved.txt> <replan.txt>"
    exit 64
  fi
  local approved="$1" replan="$2"

  if [[ ! -f "$approved" ]]; then
    err "No approved pre-gate plan for this stack — cannot apply a saved plan; re-plan required."
    echo "DIVERGENCE: approved plan '${approved}' is absent." >&2
    exit 3
  fi

  local approved_counts replan_counts
  approved_counts="$(plan_counts "$approved")"
  replan_counts="$(plan_counts "$replan")"

  local approved_addrs replan_addrs
  approved_addrs="$(plan_addresses "$approved")"
  replan_addrs="$(plan_addresses "$replan")"

  if [[ "$approved_counts" == "$replan_counts" && "$approved_addrs" == "$replan_addrs" ]]; then
    echo "plan-gate: re-plan matches approved plan (counts '${approved_counts}'); apply may proceed."
    return 0
  fi

  err "Re-plan DIVERGES from the approved plan — failing closed (no downstream applies)."
  {
    echo "### Divergence diff"
    echo "approved counts (add change destroy): ${approved_counts}"
    echo "re-plan  counts (add change destroy): ${replan_counts}"
    echo "--- approved addresses ---"
    echo "${approved_addrs}"
    echo "--- re-plan addresses ---"
    echo "${replan_addrs}"
    echo "--- address diff (approved vs re-plan) ---"
    diff <(echo "${approved_addrs}") <(echo "${replan_addrs}") || true
  } >&2
  exit 3
}

cmd_counts() {
  if [[ "$#" -ne 1 ]]; then
    err "usage: plan_gate_check.sh counts <plan.txt>"
    exit 64
  fi
  plan_counts "$1"
}

main() {
  local sub="${1:-}"
  case "$sub" in
    destroy-ack) shift; cmd_destroy_ack "$@" ;;
    plan-diff)   shift; cmd_plan_diff "$@" ;;
    counts)      shift; cmd_counts "$@" ;;
    -h|--help|"")
      cat >&2 <<'USAGE'
plan_gate_check.sh — informed-gate safety checks over terraform plan text.
  destroy-ack <ack> <plan.txt> [plan.txt ...]   destroy acknowledgment gate (ADR-R6-4)
  plan-diff   <approved.txt> <replan.txt>        cross-stack divergence gate (ADR-R6-5)
USAGE
      exit 64
      ;;
    *)
      err "unknown subcommand '${sub}'"
      exit 64
      ;;
  esac
}

main "$@"
