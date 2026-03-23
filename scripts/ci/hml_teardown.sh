#!/usr/bin/env bash
# Tears down the ephemeral HML environment created by hml_provision.sh:
#   - Stops and deregisters ECS tasks/task definitions
#   - Deletes ECS cluster + security group
#
# Persistent resources (Kinesis, SQS, Firehose, DynamoDB, CloudWatch, S3) are
# managed by Terraform (services/hml/04_peripherals) and are NOT deleted here.
#
# Workflow-level env vars used directly (auto-available on runner):
#   HML_ECS_CLUSTER — e.g. dm-hml-ecs
#   AWS_REGION      — e.g. sa-east-1
#
# Required env vars (must be set in workflow step env:):
#   HML_SG_ID — security group ID from the provision step outputs
set -euo pipefail

REGION="${AWS_REGION}"

# ── Stop ECS tasks ─────────────────────────────────────────────────────────────
echo "==> Stopping HML ECS tasks..."
TASKS=$(aws ecs list-tasks --cluster "${HML_ECS_CLUSTER}" \
  --query 'taskArns' --output json 2>/dev/null || echo '[]')
for TASK_ARN in $(echo "$TASKS" | jq -r '.[]'); do
  aws ecs stop-task --cluster "${HML_ECS_CLUSTER}" --task "$TASK_ARN" \
    --reason "HML teardown" 2>/dev/null || true
done

# ── Deregister task definitions ────────────────────────────────────────────────
echo "==> Deregistering HML task definitions..."
for FAMILY in hml-dm-mined-blocks-watcher hml-dm-orphan-blocks-watcher \
              hml-dm-block-data-crawler hml-dm-mined-txs-crawler hml-dm-txs-input-decoder; do
  REVISIONS=$(aws ecs list-task-definitions --family-prefix "$FAMILY" \
    --query 'taskDefinitionArns' --output json 2>/dev/null || echo '[]')
  for ARN in $(echo "$REVISIONS" | jq -r '.[]'); do
    aws ecs deregister-task-definition --task-definition "$ARN" \
      --query 'taskDefinition.taskDefinitionArn' --output text 2>/dev/null || true
  done
done

# ── Delete ECS cluster + security group ───────────────────────────────────────
echo "==> Deleting HML ECS cluster..."
aws ecs delete-cluster --cluster "${HML_ECS_CLUSTER}" 2>/dev/null || true

if [ -n "${HML_SG_ID:-}" ]; then
  echo "==> Deleting HML security group ${HML_SG_ID} (waiting 20s for tasks to stop)..."
  sleep 20
  aws ec2 delete-security-group --group-id "${HML_SG_ID}" 2>/dev/null || true
fi

echo "==> HML teardown complete."
