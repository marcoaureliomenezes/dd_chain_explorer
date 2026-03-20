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
#   DYNAMODB_TABLE
#
# HML secrets:
#   HML_VPC_ID, HML_SUBNET_ID
#   ECS_TASK_EXECUTION_ROLE_ARN, ECS_TASK_ROLE_ARN
#   DATABRICKS_HML_HOST, DATABRICKS_HML_TOKEN
#   HML_ETHERSCAN_SSM_PATH
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

# ---- DynamoDB table name (single-table design) -----------------------------
echo ""
echo "--- DynamoDB table name ---"
echo "  Hint: PROD table name from 'make dev_tf_output' or Terraform output."
echo "        Default: dm-chain-explorer"
read -rp "  Enter DYNAMODB_TABLE [dm-chain-explorer]: " TBL1
set_secret "DYNAMODB_TABLE" "${TBL1:-dm-chain-explorer}"

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

# ---- HML Infrastructure Secrets --------------------------------------------
echo ""
echo "--- HML Infrastructure Secrets ---"
echo "  Hint: Run 'make hml_tf_output' to get ECS role ARNs."
echo "        Run 'make hml_tf_apply' first if HML terraform not yet applied."
echo ""

read -rp  "  Enter HML_VPC_ID     (e.g. vpc-0abc123...): "          HML_VPC_ID
read -rp  "  Enter HML_SUBNET_ID  (public subnet in HML VPC): "    HML_SUBNET_ID
set_secret "HML_VPC_ID"    "$HML_VPC_ID"
set_secret "HML_SUBNET_ID" "$HML_SUBNET_ID"

echo ""
echo "  Hint: Copy values from 'make hml_tf_output' (services/hml/1_aws_core/)"
read -rp  "  Enter ECS_TASK_EXECUTION_ROLE_ARN (hml_ecs_task_execution_role_arn): " EXEC_ROLE_ARN
read -rp  "  Enter ECS_TASK_ROLE_ARN           (hml_ecs_task_role_arn):           " TASK_ROLE_ARN
set_secret "ECS_TASK_EXECUTION_ROLE_ARN" "$EXEC_ROLE_ARN"
set_secret "ECS_TASK_ROLE_ARN"           "$TASK_ROLE_ARN"

echo ""
echo "--- Databricks HML workspace (Free Edition) ---"
echo "  Hint: Databricks Free Edition workspace URL + personal access token."
read -rp  "  Enter DATABRICKS_HML_HOST  (e.g. https://community.cloud.databricks.com): " DBX_HML_HOST
read -rsp "  Enter DATABRICKS_HML_TOKEN (dapi...): " DBX_HML_TOKEN; echo
set_secret "DATABRICKS_HML_HOST"  "$DBX_HML_HOST"
set_secret "DATABRICKS_HML_TOKEN" "$DBX_HML_TOKEN"

echo ""
echo "--- HML Batch Integration Test ---"
echo "  Hint: SSM Parameter Store path containing an Etherscan API key."
echo "        Example: /etherscan-api-keys/key-1"
echo "        The ECS_TASK_ROLE_ARN must have secretsmanager:GetSecretValue on"
echo "        arn:aws:secretsmanager:<region>:*:secret:dm-chain-explorer-hml-*"
read -rp  "  Enter HML_ETHERSCAN_SSM_PATH (SSM path, not the key value): " HML_ETH_SSM
set_secret "HML_ETHERSCAN_SSM_PATH" "$HML_ETH_SSM"

# ---- GitHub environments ----------------------------------------------------
echo ""
echo "--- GitHub environments ---"
create_environment "dev"
create_environment "hml"
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
