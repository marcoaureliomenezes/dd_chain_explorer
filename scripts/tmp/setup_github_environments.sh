#!/usr/bin/env bash
# scripts/setup_github_environments.sh
#
# Configures GitHub Environments and branch protection rules for
# dd_chain_explorer via the gh CLI.
#
# Environments created:
#   hml        — auto (no approval, no wait timer)
#   production — manual approval (1 reviewer, prevent self-review)
#
# Branch protection rules:
#   master  — PRs only, 1 required review, no direct push, no force push
#   develop — PRs only, 1 required review, no direct push, no force push
#
# Prerequisites:
#   gh CLI authenticated with admin scope on the repository:
#     gh auth login   (select repo + admin:org when prompted)
#
# Usage:
#   chmod +x scripts/setup_github_environments.sh
#   ./scripts/setup_github_environments.sh [--repo owner/repo]
#
set -euo pipefail

# ---- Defaults ---------------------------------------------------------------
REPO=""

# ---- Argument parsing -------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

# Auto-detect repo from git remote if not provided
if [ -z "$REPO" ]; then
  REPO=$(git remote get-url origin 2>/dev/null \
    | sed -E 's|.*github\.com[:/]||; s|\.git$||')
  if [ -z "$REPO" ]; then
    echo "ERROR: Could not detect GitHub repo. Pass --repo owner/repo"
    exit 1
  fi
fi

# ---- Verify gh CLI is available and authenticated ---------------------------
if ! command -v gh &>/dev/null; then
  echo "ERROR: gh CLI not found. Install from https://cli.github.com/"
  exit 1
fi

if ! gh auth status &>/dev/null 2>&1; then
  echo "ERROR: gh CLI not authenticated. Run: gh auth login"
  exit 1
fi

echo ""
echo "=== Configuring GitHub Environments & Branch Protection for: $REPO ==="
echo ""

# ---- Helper: get authenticated user (for reviewer) -------------------------
GH_USER=$(gh api /user --jq '.login' 2>/dev/null || echo "")

# ---- Helper: get user ID for reviewer --------------------------------------
GH_USER_ID=""
if [ -n "$GH_USER" ]; then
  GH_USER_ID=$(gh api "/users/${GH_USER}" --jq '.id' 2>/dev/null || echo "")
fi

# =============================================================================
# Environments
# =============================================================================

echo "--- GitHub Environments ---"

# ---- hml: auto (no approval) ------------------------------------------------
echo "  Creating 'hml' environment (auto, no approval)..."
gh api --method PUT "/repos/${REPO}/environments/hml" \
  --field "wait_timer=0" \
  --field "prevent_self_review=false" \
  --field "deployment_branch_policy=null" \
  --silent 2>/dev/null || \
gh api --method PUT "/repos/${REPO}/environments/hml" \
  -f wait_timer=0 \
  --silent
echo "[OK]   environment 'hml' created (auto, no approval)"

# ---- production: manual approval with 1 reviewer ---------------------------
echo "  Creating 'production' environment (manual approval, 1 reviewer)..."
if [ -n "$GH_USER_ID" ]; then
  gh api --method PUT "/repos/${REPO}/environments/production" \
    --input - <<JSON
{
  "wait_timer": 0,
  "prevent_self_review": true,
  "reviewers": [
    {"type": "User", "id": ${GH_USER_ID}}
  ]
}
JSON
  echo "[OK]   environment 'production' created (reviewer: @${GH_USER})"
else
  gh api --method PUT "/repos/${REPO}/environments/production" \
    -f wait_timer=0 \
    --silent
  echo "[OK]   environment 'production' created (add reviewers manually at Settings → Environments)"
fi

echo ""

# =============================================================================
# Branch Protection Rules
# =============================================================================

echo "--- Branch Protection Rules ---"

# ---- Helper to apply branch protection -------------------------------------
protect_branch() {
  local BRANCH="$1"
  local DESCRIPTION="$2"

  echo "  Applying protection to '${BRANCH}' (${DESCRIPTION})..."

  gh api --method PUT "/repos/${REPO}/branches/${BRANCH}/protection" \
    --input - <<'JSON'
{
  "required_status_checks": null,
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "dismissal_restrictions": {},
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "required_approving_review_count": 1,
    "require_last_push_approval": false
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": false,
  "lock_branch": false,
  "allow_fork_syncing": false
}
JSON

  if [ $? -eq 0 ]; then
    echo "[OK]   '${BRANCH}' — PR required, 1 review, no force push, no direct push"
  else
    echo "[FAIL] '${BRANCH}' — check admin permissions on the repository"
  fi
}

protect_branch "master"  "production branch"
echo ""
protect_branch "develop" "integration branch"

echo ""
echo "=== Done. Verify at: https://github.com/${REPO}/settings/branches ==="
echo ""
echo "⚠️  Manual steps required after running this script:"
echo "   1. Go to https://github.com/${REPO}/settings/environments/production"
echo "      → Add yourself (or a team) as a required reviewer if not already set."
echo "   2. Review branch protection rules at Settings → Branches."
echo "   3. Ensure all 5 deploy workflows use 'environment: production' for prod jobs."
echo ""
