#!/usr/bin/env bash
# scripts/setup_github_secrets.sh
#
# Configures all required GitHub Actions secrets and environments for
# dd_chain_explorer.  Works with either the `gh` CLI or the GitHub REST API
# + PyNaCl (python3 package).
#
# Secrets created:
#   AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
#   DATABRICKS_ACCOUNT_ID, DATABRICKS_CLIENT_ID, DATABRICKS_CLIENT_SECRET
#   DATABRICKS_PROD_HOST, DATABRICKS_PROD_TOKEN
#   MSK_BOOTSTRAP_SERVERS
#   DYNAMODB_SEMAPHORE_TABLE, DYNAMODB_CONSUMPTION_TABLE,
#   DYNAMODB_POPULAR_CONTRACTS_TABLE
#
# Prerequisites (one of the two):
#   Option A — gh CLI:  gh auth login  (needs repo + secrets scope)
#   Option B — curl:    export GITHUB_TOKEN=ghp_yourPAT  (needs repo scope)
#                       pip install pynacl
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

OWNER="${REPO%%/*}"
REPO_NAME="${REPO##*/}"
GH_API="https://api.github.com"

echo ""
echo "=== Setting up GitHub secrets for: $REPO ==="
echo "=== AWS profile: $AWS_PROFILE ==="
echo ""

# ---- Check available tools --------------------------------------------------
USE_GH_CLI=false
USE_CURL_API=false

if command -v gh &>/dev/null && gh auth status &>/dev/null 2>&1; then
  USE_GH_CLI=true
  echo "[INFO] Using gh CLI to set secrets"
elif [[ -n "${GITHUB_TOKEN:-}" ]]; then
  # Check for PyNaCl
  if python3 -c "import nacl" &>/dev/null 2>&1; then
    USE_CURL_API=true
    echo "[INFO] Using GitHub REST API (curl + PyNaCl) to set secrets"
  else
    echo "[WARN] PyNaCl not installed. Installing..."
    pip install pynacl -q || pip install --user pynacl -q || true
    if python3 -c "import nacl" &>/dev/null 2>&1; then
      USE_CURL_API=true
    else
      echo "[ERROR] Could not install PyNaCl. Please install: pip install pynacl"
      echo "        Or use: gh auth login && run this script again"
      exit 1
    fi
  fi
else
  echo "[ERROR] No authentication available. Either:"
  echo "  Option A: Install and authenticate gh CLI:  gh auth login"
  echo "  Option B: export GITHUB_TOKEN=ghp_yourPAThere"
  exit 1
fi

# ---- Helper: get repo public key for encryption ----------------------------
_get_pub_key_json() {
  curl -sS -H "Authorization: token ${GITHUB_TOKEN}" \
    "${GH_API}/repos/${OWNER}/${REPO_NAME}/actions/secrets/public-key"
}

# ---- Helper: set a single secret --------------------------------------------
set_secret() {
  local NAME="$1"
  local VALUE="$2"
  if [ -z "$VALUE" ]; then
    echo "[SKIP] $NAME is empty — skipping"
    return
  fi

  if $USE_GH_CLI; then
    printf '%s' "$VALUE" | gh secret set "$NAME" --repo "$REPO"
    echo "[OK]   $NAME (gh CLI)"
    return
  fi

  # curl + PyNaCl path
  local pk_json key_id key_b64 encrypted_b64
  pk_json=$(_get_pub_key_json)
  key_id=$(python3 -c "import sys,json; d=json.loads('''${pk_json}'''); print(d['key_id'])")
  key_b64=$(python3 -c "import sys,json; d=json.loads('''${pk_json}'''); print(d['key'])")

  encrypted_b64=$(python3 - <<PYEOF
import base64
from nacl import encoding, public
pub_key = public.PublicKey(base64.b64decode("${key_b64}"), encoding.RawEncoder)
box = public.SealedBox(pub_key)
encrypted = box.encrypt(b"${VALUE}")
print(base64.b64encode(encrypted).decode())
PYEOF
)

  local http_code
  http_code=$(curl -sS -o /dev/null -w "%{http_code}" \
    -X PUT \
    -H "Authorization: token ${GITHUB_TOKEN}" \
    -H "Content-Type: application/json" \
    "${GH_API}/repos/${OWNER}/${REPO_NAME}/actions/secrets/${NAME}" \
    -d "{\"encrypted_value\":\"${encrypted_b64}\",\"key_id\":\"${key_id}\"}")

  if [[ "$http_code" == "201" || "$http_code" == "204" ]]; then
    echo "[OK]   $NAME (HTTP ${http_code})"
  else
    echo "[FAIL] $NAME — HTTP ${http_code}"
  fi
}

# ---- Helper: create GitHub environment --------------------------------------
create_environment() {
  local env_name="$1"
  echo "  Creating environment: ${env_name}"
  if $USE_GH_CLI; then
    gh api --method PUT "/repos/${REPO}/environments/${env_name}" \
      -f wait_timer=0 &>/dev/null || true
  else
    curl -sS -o /dev/null \
      -X PUT \
      -H "Authorization: token ${GITHUB_TOKEN}" \
      -H "Content-Type: application/json" \
      "${GH_API}/repos/${OWNER}/${REPO_NAME}/environments/${env_name}" \
      -d '{"wait_timer":0,"prevent_self_review":false,"reviewers":[]}'
  fi
  echo "[OK]   environment '${env_name}' created/updated"
}

# ---- AWS credentials --------------------------------------------------------
echo "--- AWS credentials (profile: $AWS_PROFILE) ---"
AWS_CREDS=$(aws configure export-credentials --profile "$AWS_PROFILE" \
  --format env 2>/dev/null || true)

if [ -n "$AWS_CREDS" ]; then
  AWS_KEY=$(echo "$AWS_CREDS" | grep "^export AWS_ACCESS_KEY_ID" \
    | sed "s/export AWS_ACCESS_KEY_ID='//;s/'//")
  AWS_SECRET=$(echo "$AWS_CREDS" | grep "^export AWS_SECRET_ACCESS_KEY" \
    | sed "s/export AWS_SECRET_ACCESS_KEY='//;s/'//")
  set_secret "AWS_ACCESS_KEY_ID"     "$AWS_KEY"
  set_secret "AWS_SECRET_ACCESS_KEY" "$AWS_SECRET"
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
echo "  Hint: AWS Console → MSK → cluster → 'View client information'"
read -rp "  Enter MSK_BOOTSTRAP_SERVERS (or press Enter to skip): " MSK_BROKERS
set_secret "MSK_BOOTSTRAP_SERVERS" "$MSK_BROKERS"

# ---- DynamoDB table names ---------------------------------------------------
echo ""
echo "--- DynamoDB table names ---"
echo "  Hint: AWS Console → DynamoDB → Tables (sa-east-1)"
read -rp "  Enter DYNAMODB_SEMAPHORE_TABLE         [dm-chain-explorer-semaphore]: " TBL1
read -rp "  Enter DYNAMODB_CONSUMPTION_TABLE       [dm-chain-explorer-consumption]: " TBL2
read -rp "  Enter DYNAMODB_POPULAR_CONTRACTS_TABLE [dm-chain-explorer-popular-contracts]: " TBL3
set_secret "DYNAMODB_SEMAPHORE_TABLE"        "${TBL1:-dm-chain-explorer-semaphore}"
set_secret "DYNAMODB_CONSUMPTION_TABLE"      "${TBL2:-dm-chain-explorer-consumption}"
set_secret "DYNAMODB_POPULAR_CONTRACTS_TABLE" "${TBL3:-dm-chain-explorer-popular-contracts}"

# ---- Databricks (DABs CLI) --------------------------------------------------
echo ""
echo "--- Databricks PROD workspace (DABs deploy) ---"
echo "  Hint: Databricks workspace URL: Settings → Developer → Access tokens"
read -rp  "  Enter DATABRICKS_PROD_HOST  (e.g. https://<id>.azuredatabricks.net): " DBX_HOST
read -rsp "  Enter DATABRICKS_PROD_TOKEN (dapi...): " DBX_TOKEN; echo
set_secret "DATABRICKS_PROD_HOST"  "$DBX_HOST"
set_secret "DATABRICKS_PROD_TOKEN" "$DBX_TOKEN"

# ---- Databricks (Terraform service principal) --------------------------------
echo ""
echo "--- Databricks service principal (Terraform AWS provider) ---"
echo "  Hint: Databricks account console → Service principals → your SP → OAuth secrets"
read -rp  "  Enter DATABRICKS_ACCOUNT_ID    (UUID): " DBX_ACCOUNT
read -rsp "  Enter DATABRICKS_CLIENT_ID     (SP app_id): " DBX_CLIENT_ID; echo
read -rsp "  Enter DATABRICKS_CLIENT_SECRET (SP secret): " DBX_CLIENT_SECRET; echo
set_secret "DATABRICKS_ACCOUNT_ID"    "$DBX_ACCOUNT"
set_secret "DATABRICKS_CLIENT_ID"     "$DBX_CLIENT_ID"
set_secret "DATABRICKS_CLIENT_SECRET" "$DBX_CLIENT_SECRET"

# ---- GitHub environments ----------------------------------------------------
echo ""
echo "--- GitHub environments ---"
create_environment "production"

echo ""
echo "=== Done. Verify at: https://github.com/$REPO/settings/secrets/actions ==="
echo ""
echo "⚠️  SECURITY REMINDERS:"
echo "   1. Rotate any secrets that may have been exposed:"
echo "      - Etherscan API keys (were in old git history — rotate at etherscan.io)"
echo "      - Alchemy/Infura API keys (SSM paths revealed — verify at alchemy.com / infura.io)"
echo "   2. Contact GitHub support to purge cached views of force-pushed commits:"
echo "      https://support.github.com/contact"
echo "   3. Install pre-commit hook to prevent future leaks:"
echo "      pip install detect-secrets && detect-secrets scan > .secrets.baseline"
echo "      pre-commit install"
