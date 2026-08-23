#!/usr/bin/env bash
# Empties every S3 bucket tagged for the given environment before a
# `terraform destroy` of that environment's peripherals stack — a non-empty
# bucket blocks bucket deletion, and Terraform's `force_destroy` is
# deliberately NOT set on these buckets (accidental-deletion guard).
#
# ECR is gone with the capture lane (T-B.2 deletes 07_ecs everywhere) — this
# script no longer touches ECR.
#
# Usage:
#   empty_s3_and_ecr.sh <dev|hml|prd>
#
# Discovery is tag-based (never a hardcoded bucket-name list): every bucket
# this project's Terraform creates carries `project=dd-chain-explorer` and
# `environment=<env>` in its default_tags (services/*/locals.tf
# `common_tags`), so a bucket renamed or added in a future release is picked
# up automatically.
#
# Workflow-level env vars used directly (auto-available on runner):
#   AWS_REGION — e.g. sa-east-1
set -euo pipefail

ENV="${1:?Usage: empty_s3_and_ecr.sh <dev|hml|prd>}"
case "$ENV" in
  dev|hml|prd) ;;
  *) echo "::error::Unknown environment '${ENV}' — expected dev, hml or prd." >&2; exit 1 ;;
esac

echo "==> Discovering S3 buckets tagged project=dd-chain-explorer, environment=${ENV}..."
BUCKET_ARNS=$(aws resourcegroupstaggingapi get-resources \
  --resource-type-filters s3 \
  --tag-filters "Key=project,Values=dd-chain-explorer" "Key=environment,Values=${ENV}" \
  --region "${AWS_REGION}" \
  --query 'ResourceTagMappingList[].ResourceARN' --output text 2>/dev/null) || BUCKET_ARNS=""

if [ -z "${BUCKET_ARNS}" ]; then
  echo "No tagged buckets found for environment=${ENV} — nothing to empty."
  exit 0
fi

for ARN in ${BUCKET_ARNS}; do
  BUCKET="${ARN##*:::}"
  BUCKET="${BUCKET#bucket/}"
  echo "==> Emptying s3://${BUCKET} (all object versions + delete markers)..."

  aws s3api list-object-versions --bucket "${BUCKET}" \
    --query '{Objects: Versions[].{Key:Key,VersionId:VersionId}}' \
    --output json 2>/dev/null | \
    python3 -c "
import json, sys
data = json.load(sys.stdin)
objs = data.get('Objects') or []
print(json.dumps({'Objects': objs}) if objs else '')
" > /tmp/versions_${BUCKET}.json 2>/dev/null || true  # idempotent — bucket may already be empty

  if [ -s "/tmp/versions_${BUCKET}.json" ]; then
    aws s3api delete-objects --bucket "${BUCKET}" \
      --delete "file:///tmp/versions_${BUCKET}.json" --region "${AWS_REGION}" 2>/dev/null || true  # idempotent teardown
  fi

  aws s3api list-object-versions --bucket "${BUCKET}" \
    --query '{Objects: DeleteMarkers[].{Key:Key,VersionId:VersionId}}' \
    --output json 2>/dev/null | \
    python3 -c "
import json, sys
data = json.load(sys.stdin)
objs = data.get('Objects') or []
print(json.dumps({'Objects': objs}) if objs else '')
" > /tmp/markers_${BUCKET}.json 2>/dev/null || true  # idempotent — bucket may already be empty

  if [ -s "/tmp/markers_${BUCKET}.json" ]; then
    aws s3api delete-objects --bucket "${BUCKET}" \
      --delete "file:///tmp/markers_${BUCKET}.json" --region "${AWS_REGION}" 2>/dev/null || true  # idempotent teardown
  fi

  rm -f "/tmp/versions_${BUCKET}.json" "/tmp/markers_${BUCKET}.json"
  echo "s3://${BUCKET} emptied."
done

echo "==> S3 cleanup complete for environment=${ENV}."
