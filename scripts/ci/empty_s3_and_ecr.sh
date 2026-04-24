#!/usr/bin/env bash
# Empties PRD ECR repositories before Terraform destroy.
# S3 buckets are protected (prevent_destroy=true) and must NOT be emptied.
#
# Workflow-level env vars used directly (auto-available on runner):
#   AWS_REGION — e.g. sa-east-1
#
# Default GitHub Actions env vars used:
#   GITHUB_WORKSPACE — path to the checked-out repository root
set -euo pipefail

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

echo "==> ECR cleanup complete. S3 buckets are protected and were NOT emptied."
