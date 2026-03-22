#!/usr/bin/env bash
# Idempotently imports pre-existing Databricks account-level resources into
# Terraform state before running plan/apply on 05a_databricks_account.
#
# Must be called from the 05a_databricks_account working directory
# (the workflow step's defaults.run.working-directory handles this).
#
# Required env vars (must be set in workflow step env:):
#   DATABRICKS_ACCOUNT_ID       — Databricks account UUID
#   DATABRICKS_CLIENT_ID        — Service principal application ID
#   DATABRICKS_CLIENT_SECRET    — Service principal client secret
#   TF_VAR_databricks_client_id — Same as DATABRICKS_CLIENT_ID (used by Terraform)
set -euo pipefail

# ── Acquire OAuth token via M2M client credentials ───────────────────────────
TOKEN=$(curl -sf -X POST \
  "https://accounts.cloud.databricks.com/oidc/accounts/${DATABRICKS_ACCOUNT_ID}/v1/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "grant_type=client_credentials" \
  --data-urlencode "client_id=${DATABRICKS_CLIENT_ID}" \
  --data-urlencode "client_secret=${DATABRICKS_CLIENT_SECRET}" \
  --data-urlencode "scope=all-apis" \
  | jq -r '.access_token' 2>/dev/null || true)

if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
  echo "::error::Could not acquire Databricks OAuth token — check DATABRICKS_CLIENT_ID/SECRET secrets."
  exit 1
fi

ACCT="https://accounts.cloud.databricks.com/api/2.0/accounts/${DATABRICKS_ACCOUNT_ID}"
AUTH="Authorization: Bearer $TOKEN"

# ── Helper: idempotent tf_import ──────────────────────────────────────────────
tf_import() {
  local label="$1" addr="$2" id="$3"
  if terraform state show "$addr" &>/dev/null; then
    echo "  ${label}: already in state — skipping."
    return 0
  fi
  if terraform import "$addr" "$id"; then
    echo "  ${label}: imported OK."
  else
    echo "  ${label}: not found in Databricks — will be created by apply."
  fi
}

echo "==> Checking for pre-existing Databricks account resources to import..."

CRED_ID=$(curl -sf -H "$AUTH" "${ACCT}/credentials" 2>/dev/null \
  | jq -r '[.[] | select(.credentials_name=="dm-chain-explorer-credentials")][0].credentials_id // empty' 2>/dev/null || true)
[ -n "$CRED_ID" ] && tf_import "MWS credentials" "databricks_mws_credentials.dm" "${DATABRICKS_ACCOUNT_ID}/${CRED_ID}"

STOR_ID=$(curl -sf -H "$AUTH" "${ACCT}/storage-configurations" 2>/dev/null \
  | jq -r '[.[] | select(.storage_configuration_name=="dm-chain-explorer-storage")][0].storage_configuration_id // empty' 2>/dev/null || true)
[ -n "$STOR_ID" ] && tf_import "MWS storage config" "databricks_mws_storage_configurations.dm" "${DATABRICKS_ACCOUNT_ID}/${STOR_ID}"

NET_ID=$(curl -sf -H "$AUTH" "${ACCT}/networks" 2>/dev/null \
  | jq -r '[.[] | select(.network_name=="dm-chain-explorer-network")][0].network_id // empty' 2>/dev/null || true)
[ -n "$NET_ID" ] && tf_import "MWS network" "databricks_mws_networks.dm" "${DATABRICKS_ACCOUNT_ID}/${NET_ID}"

WS_ID=$(curl -sf -H "$AUTH" "${ACCT}/workspaces" 2>/dev/null \
  | jq -r '[.[] | select(.workspace_name=="dm-chain-explorer-prd")][0].workspace_id // empty' 2>/dev/null || true)
[ -n "$WS_ID" ] && tf_import "MWS workspace" "databricks_mws_workspaces.dm" "${DATABRICKS_ACCOUNT_ID}/${WS_ID}"

MS_ID=$(curl -sf -H "$AUTH" "https://accounts.cloud.databricks.com/api/2.1/unity-catalog/metastores" 2>/dev/null \
  | jq -r '[.metastores[]? | select(.name=="dm-chain-explorer-metastore")][0].metastore_id // empty' 2>/dev/null || true)

# Fallback: read metastore_id from TF state if API returned nothing
if [ -z "${MS_ID:-}" ]; then
  MS_ID=$(terraform state show databricks_metastore.dm 2>/dev/null \
    | grep -E '^\s+id\s*=' | head -1 | sed 's/.*=\s*"\(.*\)"/\1/' || true)
  [ -n "$MS_ID" ] && echo "  Metastore ID read from TF state: $MS_ID"
fi
[ -n "$MS_ID" ] && tf_import "Unity Catalog metastore" "databricks_metastore.dm" "$MS_ID"

if [ -n "${WS_ID:-}" ] && [ -n "${MS_ID:-}" ]; then
  tf_import "Metastore assignment" "databricks_metastore_assignment.dm" "${WS_ID}/${MS_ID}"
fi

if [ -n "${MS_ID:-}" ]; then
  SC_NAME="dm-metastore-data-access"
  tf_import "Metastore data access" "databricks_metastore_data_access.default" "${MS_ID}|${SC_NAME}"
fi

# ── Import MWS permission assignments if workspace exists ────────────────────
if [ -n "${WS_ID:-}" ]; then
  PA_JSON=$(curl -sf -H "$AUTH" \
    "${ACCT}/workspaces/${WS_ID}/permissionassignments" 2>/dev/null \
    | jq -r '[.permission_assignments[]? | select(any(.permissions[]?; . == "ADMIN")) | .principal.principal_id]' 2>/dev/null || true)

  # Import user admin assignment (first non-SP principal that is a user)
  PA_USER=$(echo "$PA_JSON" | jq -r '.[0] // empty' 2>/dev/null || true)
  [ -n "$PA_USER" ] && tf_import "MWS permission assignment (admin user)" \
    "databricks_mws_permission_assignment.admin" "${WS_ID}|${PA_USER}"

  # Import SP admin assignment — look up principal_id by applicationId
  SP_PRINCIPAL_ID=$(curl -sf -H "$AUTH" \
    "${ACCT}/servicePrincipals" 2>/dev/null \
    | jq -r --arg cid "${TF_VAR_databricks_client_id}" \
      '[.Resources[]? | select(.applicationId==($cid|tonumber))][0].id // empty' 2>/dev/null || true)
  if [ -n "$SP_PRINCIPAL_ID" ]; then
    SP_PA_ID=$(echo "$PA_JSON" | jq -r --arg pid "$SP_PRINCIPAL_ID" \
      'map(select(. == ($pid|tonumber))) | .[0] // empty' 2>/dev/null || true)
    [ -n "$SP_PA_ID" ] && tf_import "MWS permission assignment (terraform SP)" \
      "databricks_mws_permission_assignment.terraform_sp" "${WS_ID}|${SP_PA_ID}"
  fi
fi

echo "==> Import check complete."
