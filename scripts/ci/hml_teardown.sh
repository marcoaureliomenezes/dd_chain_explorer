#!/usr/bin/env bash
# Tears down the ephemeral HML environment created by hml_provision.sh:
#   - Stops running ECS tasks
#   - Deletes the ephemeral security group
#
# Persistent resources (DynamoDB, CloudWatch log group, S3) are managed by
# Terraform (services/hml/04_peripherals) and are NOT deleted here. The streaming
# capture layer (Kinesis/SQS/Firehose + the 5 producer task-defs) was retired in
# v0.4.0 — capture now runs in the separate dd-chain-capture project.
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
    --reason "HML teardown" 2>/dev/null || true  # idempotent teardown — task may already be stopped/gone
done

# ── Deregister task definitions ────────────────────────────────────────────────
# The 5 streaming-producer task-def families were retired in v0.4.0 (capture now
# runs in the dd-chain-capture project), so there are no producer families to
# deregister here. Any surviving ephemeral task defs are cleaned by their own
# provision step; nothing capture-related remains to tear down.

# ── Delete security group ─────────────────────────────────────────────────────
# ECS cluster is Terraform-managed (services/hml/07_ecs) — NOT deleted here.
if [ -n "${HML_SG_ID:-}" ]; then
  echo "==> Deleting HML security group ${HML_SG_ID} (waiting 20s for tasks to stop)..."
  sleep 20
  aws ec2 delete-security-group --group-id "${HML_SG_ID}" 2>/dev/null || true  # idempotent teardown — SG may already be deleted
fi

echo "==> HML teardown complete."
