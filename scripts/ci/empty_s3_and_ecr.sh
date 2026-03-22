#!/usr/bin/env bash
# Empties PRD S3 buckets (all object versions + delete markers) and ECR
# repositories before Terraform destroy, which requires them to be empty.
#
# Workflow-level env vars used directly (auto-available on runner):
#   AWS_REGION — e.g. sa-east-1
#
# Default GitHub Actions env vars used:
#   GITHUB_WORKSPACE — path to the checked-out repository root
set -euo pipefail

# ── S3 buckets ────────────────────────────────────────────────────────────────
echo "==> Emptying PRD S3 buckets..."
chmod +x "${GITHUB_WORKSPACE}/scripts/empty_s3_bucket.sh"
for BUCKET in dm-chain-explorer-raw-data dm-chain-explorer-lakehouse dm-chain-explorer-databricks; do
  if aws s3api head-bucket --bucket "${BUCKET}" 2>/dev/null; then
    bash "${GITHUB_WORKSPACE}/scripts/empty_s3_bucket.sh" "${BUCKET}" "${AWS_REGION}"
  else
    echo "Bucket ${BUCKET} does not exist — skipping."
  fi
done

# ── ECR repositories ──────────────────────────────────────────────────────────
echo "==> Emptying PRD ECR repositories..."
for REPO in onchain-stream-txs onchain-batch-txs; do
  IMAGES=$(aws ecr list-images --repository-name "${REPO}" --region "${AWS_REGION}" \
    --query 'imageIds[*]' --output json 2>/dev/null) || IMAGES="[]"
  if [ "${IMAGES}" != "[]" ] && [ -n "${IMAGES}" ]; then
    aws ecr batch-delete-image --repository-name "${REPO}" \
      --image-ids "${IMAGES}" --region "${AWS_REGION}" 2>/dev/null || true
    echo "ECR ${REPO} emptied."
  else
    echo "ECR ${REPO} is empty or does not exist — skipping."
  fi
done

echo "==> S3 + ECR cleanup complete."
