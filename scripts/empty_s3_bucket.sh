#!/usr/bin/env bash
# empty_s3_bucket.sh — Empties an S3 bucket so Terraform can destroy it.
#
# Usage:
#   ./scripts/empty_s3_bucket.sh <bucket-name> [aws-region]
#
# Returns 0 if the bucket is already empty or was successfully emptied.
# Returns 1 on unexpected errors.

set -euo pipefail

BUCKET="${1:?Usage: $0 <bucket-name> [aws-region]}"
REGION="${2:-sa-east-1}"

echo ">>> Emptying S3 bucket: s3://${BUCKET} (region: ${REGION})"

# ── 1. Delete all current objects ────────────────────────────────────────────
echo "  [1/3] Removing all objects..."
aws s3 rm "s3://${BUCKET}" --recursive --region "${REGION}" 2>/dev/null || true

# ── 2. Delete all non-current versions (if versioning was ever enabled) ──────
echo "  [2/3] Removing object versions..."
while true; do
  VERSIONS=$(aws s3api list-object-versions \
    --bucket "${BUCKET}" \
    --region "${REGION}" \
    --query 'Versions[].{Key:Key,VersionId:VersionId}' \
    --output json 2>/dev/null || echo "[]")

  if [ -z "${VERSIONS}" ] || [ "${VERSIONS}" = "[]" ] || [ "${VERSIONS}" = "null" ]; then
    break
  fi

  # Write payload to a temp file to avoid "Argument list too long" with large buckets
  TMP_PAYLOAD=$(mktemp /tmp/s3_delete_payload.XXXXXX.json)
  echo "${VERSIONS}" | jq '{Objects: [.[] | select(.Key and .VersionId) | {Key,VersionId}], Quiet: true}' > "${TMP_PAYLOAD}"
  OBJCOUNT=$(jq '.Objects | length' < "${TMP_PAYLOAD}")
  if [ "${OBJCOUNT}" -eq 0 ]; then
    rm -f "${TMP_PAYLOAD}"
    break
  fi
  aws s3api delete-objects \
    --bucket "${BUCKET}" \
    --delete "file://${TMP_PAYLOAD}" \
    --region "${REGION}" > /dev/null
  rm -f "${TMP_PAYLOAD}"
done

# ── 3. Delete all delete markers ─────────────────────────────────────────────
echo "  [3/3] Removing delete markers..."
while true; do
  MARKERS=$(aws s3api list-object-versions \
    --bucket "${BUCKET}" \
    --region "${REGION}" \
    --query 'DeleteMarkers[].{Key:Key,VersionId:VersionId}' \
    --output json 2>/dev/null || echo "[]")

  if [ -z "${MARKERS}" ] || [ "${MARKERS}" = "[]" ] || [ "${MARKERS}" = "null" ]; then
    break
  fi

  # Write payload to a temp file to avoid "Argument list too long" with large buckets
  TMP_PAYLOAD=$(mktemp /tmp/s3_delete_payload.XXXXXX.json)
  echo "${MARKERS}" | jq '{Objects: [.[] | select(.Key and .VersionId) | {Key,VersionId}], Quiet: true}' > "${TMP_PAYLOAD}"
  OBJCOUNT=$(jq '.Objects | length' < "${TMP_PAYLOAD}")
  if [ "${OBJCOUNT}" -eq 0 ]; then
    rm -f "${TMP_PAYLOAD}"
    break
  fi
  aws s3api delete-objects \
    --bucket "${BUCKET}" \
    --delete "file://${TMP_PAYLOAD}" \
    --region "${REGION}" > /dev/null
  rm -f "${TMP_PAYLOAD}"
done

echo ">>> Bucket s3://${BUCKET} is now empty."
