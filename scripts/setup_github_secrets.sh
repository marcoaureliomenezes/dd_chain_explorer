#!/usr/bin/env bash
# scripts/setup_github_secrets.sh
#
# Configures all required GitHub Actions secrets for dd_chain_explorer using
# the GitHub CLI (gh). Run once after forking/cloning the repository.
#
# Prerequisites:
#   - gh CLI installed and authenticated: gh auth login
#   - AWS CLI installed and a profile with sufficient IAM permissions
#   - jq installed
#
# Usage:
#   chmod +x scripts/setup_github_secrets.sh
#   ./scripts/setup_github_secrets.sh [--repo owner/repo] [--aws-profile <profile>]
#
set -euo pipefail

# ---- Defaults ---------------------------------------------------------------
REPO=""
AWS_PROFILE="${AWS_PROFILE:-default}"

# ---- Argument parsing -------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)         REPO="$2"; shift 2 ;;
    --aws-profile)  AWS_PROFILE="$2"; shift 2 ;;
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

echo ""
echo "=== Setting up GitHub secrets for: $REPO ==="
echo "=== AWS profile: $AWS_PROFILE ==="
echo ""

# ---- Helper -----------------------------------------------------------------
set_secret() {
  local NAME="$1"
  local VALUE="$2"
  if [ -z "$VALUE" ]; then
    echo "[SKIP] $NAME is empty — skipping"
    return
  fi
  echo "$VALUE" | gh secret set "$NAME" --repo "$REPO" --body -
  echo "[OK]   $NAME"
}

# ---- AWS credentials --------------------------------------------------------
echo "--- AWS credentials (profile: $AWS_PROFILE) ---"
AWS_CREDS=$(aws configure export-credentials --profile "$AWS_PROFILE" \
  --format env 2>/dev/null || true)

if [ -n "$AWS_CREDS" ]; then
  AWS_ACCESS_KEY_ID=$(echo "$AWS_CREDS" | grep "^export AWS_ACCESS_KEY_ID" \
    | sed "s/export AWS_ACCESS_KEY_ID='//;s/'//")
  AWS_SECRET_ACCESS_KEY=$(echo "$AWS_CREDS" | grep "^export AWS_SECRET_ACCESS_KEY" \
    | sed "s/export AWS_SECRET_ACCESS_KEY='//;s/'//")
  set_secret "AWS_ACCESS_KEY_ID"     "$AWS_ACCESS_KEY_ID"
  set_secret "AWS_SECRET_ACCESS_KEY" "$AWS_SECRET_ACCESS_KEY"
else
  echo "[WARN] Could not read AWS credentials from profile '$AWS_PROFILE'."
  read -rsp "  Enter AWS_ACCESS_KEY_ID: " AWS_KEY; echo
  read -rsp "  Enter AWS_SECRET_ACCESS_KEY: " AWS_SECRET; echo
  set_secret "AWS_ACCESS_KEY_ID"     "$AWS_KEY"
  set_secret "AWS_SECRET_ACCESS_KEY" "$AWS_SECRET"
fi

# ---- MSK Bootstrap Servers --------------------------------------------------
echo ""
echo "--- MSK Bootstrap Servers ---"
echo "  Hint: AWS Console → MSK → your cluster → 'View client information'"
read -rp "  Enter MSK_BOOTSTRAP_SERVERS (or press Enter to skip): " MSK_BROKERS
set_secret "MSK_BOOTSTRAP_SERVERS" "$MSK_BROKERS"

# ---- Databricks -------------------------------------------------------------
echo ""
echo "--- Databricks (PROD workspace) ---"
echo "  Hint: Databricks workspace URL looks like https://<id>.azuredatabricks.net"
echo "  or https://<id>.cloud.databricks.com"
read -rp  "  Enter DATABRICKS_PROD_HOST (or press Enter to skip): " DBX_HOST
read -rsp "  Enter DATABRICKS_PROD_TOKEN (or press Enter to skip): " DBX_TOKEN; echo
set_secret "DATABRICKS_PROD_HOST"  "$DBX_HOST"
set_secret "DATABRICKS_PROD_TOKEN" "$DBX_TOKEN"

echo ""
echo "=== Done. Verify secrets at: https://github.com/$REPO/settings/secrets/actions ==="
