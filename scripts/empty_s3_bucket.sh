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

# ── 2 + 3. Delete all versions and delete markers via boto3 ──────────────────
# Using Python/boto3 instead of aws-cli shell one-liners to avoid:
#   - "Argument list too long" when bucket has many versioned objects
#   - MalformedXML edge-cases in aws-cli JSON→XML conversion
echo "  [2/3] Removing object versions and delete markers (boto3)..."
python3 - "${BUCKET}" "${REGION}" << 'PYEOF'
import sys, boto3

bucket, region = sys.argv[1], sys.argv[2]
s3 = boto3.client("s3", region_name=region)

deleted_total = 0
while True:
    resp = s3.list_object_versions(Bucket=bucket, MaxKeys=500)
    to_delete = (
        [{"Key": v["Key"], "VersionId": v["VersionId"]} for v in resp.get("Versions", [])]
        + [{"Key": m["Key"], "VersionId": m["VersionId"]} for m in resp.get("DeleteMarkers", [])]
    )
    if not to_delete:
        break
    s3.delete_objects(Bucket=bucket, Delete={"Objects": to_delete, "Quiet": True})
    deleted_total += len(to_delete)
    print(f"  ... deleted {deleted_total} versions/markers so far")

print(f"  Done ({deleted_total} total versions/markers removed).")
PYEOF

echo ">>> Bucket s3://${BUCKET} is now empty."
