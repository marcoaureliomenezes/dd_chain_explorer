#!/usr/bin/env bash
# Validates Databricks host/token pairing for a target environment.
# Required env vars:
#   TARGET_ENV                -> hml | prd
#   DATABRICKS_HOST           -> active host used by the step
#   DATABRICKS_TOKEN          -> active token used by the step
#   DATABRICKS_HML_HOST       -> HML host reference
#   DATABRICKS_PROD_HOST      -> PRD host reference
#   DATABRICKS_HML_TOKEN      -> HML token reference
#   DATABRICKS_PROD_TOKEN     -> PRD token reference
set -euo pipefail

required_vars=(
  TARGET_ENV
  DATABRICKS_HOST
  DATABRICKS_TOKEN
  DATABRICKS_HML_HOST
  DATABRICKS_PROD_HOST
  DATABRICKS_HML_TOKEN
  DATABRICKS_PROD_TOKEN
)

for name in "${required_vars[@]}"; do
  if [ -z "${!name:-}" ]; then
    echo "::error::Missing required env var: ${name}"
    exit 1
  fi
done

case "${TARGET_ENV}" in
  hml)
    if [ "${DATABRICKS_HOST}" != "${DATABRICKS_HML_HOST}" ]; then
      echo "::error::Invalid host/token pairing for HML: host is not HML."
      exit 1
    fi
    if [ "${DATABRICKS_TOKEN}" != "${DATABRICKS_HML_TOKEN}" ]; then
      echo "::error::Invalid host/token pairing for HML: token is not HML."
      exit 1
    fi
    ;;
  prd)
    if [ "${DATABRICKS_HOST}" != "${DATABRICKS_PROD_HOST}" ]; then
      echo "::error::Invalid host/token pairing for PRD: host is not PRD."
      exit 1
    fi
    if [ "${DATABRICKS_TOKEN}" != "${DATABRICKS_PROD_TOKEN}" ]; then
      echo "::error::Invalid host/token pairing for PRD: token is not PRD."
      exit 1
    fi
    if [ "${DATABRICKS_TOKEN}" = "${DATABRICKS_HML_TOKEN}" ]; then
      echo "::error::Invalid host/token pairing for PRD: PRD token equals HML token."
      exit 1
    fi
    ;;
  *)
    echo "::error::Unsupported TARGET_ENV '${TARGET_ENV}'. Expected: hml | prd"
    exit 1
    ;;
esac

echo "Databricks host/token pairing validated for TARGET_ENV=${TARGET_ENV}."
